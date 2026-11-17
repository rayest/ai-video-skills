#!/bin/bash
# Render every scene (one guarded process each), build the soundtrack, concat, mux.
# Expects: assets/ (the showcase images named in render.py) and build/vo/ (from tts_doubao.py).
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-python3}"                  # a Python with numpy + Pillow
GUARD="${GUARD:-mem-guard --wait}"   # set GUARD= to run without tools/mem-guard
SC="s00 s01 s02 s03 s04 s05 s06 s07 s08 s09 s10"
mkdir -p build/seg
for s in ${ONLY:-$SC}; do
  $GUARD --max 1400M -- $PY -I render.py $s
  echo "rendered $s"
done
$GUARD --max 900M -- $PY -I audio.py
: > build/concat.txt
for s in $SC; do echo "file 'seg/$s.mp4'" >> build/concat.txt; done
$GUARD --max 800M -- ffmpeg -v error -y -f concat -safe 0 -i build/concat.txt -i build/audio_mix.wav \
  -threads 2 -map 0:v -map 1:a -af loudnorm=I=-14:TP=-1.5:LRA=7 -c:v copy -c:a aac -b:a 192k -ar 44100 -ac 2 -shortest -movflags +faststart \
  out.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4
