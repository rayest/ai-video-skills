# Render pipeline

Written for a small server (2 cores, 4 GB RAM, no swap); it works the same on a laptop. Memory rules: `tools/LOW-MEMORY.md`.

## Process layout

- One scene (≤ 15 s) per process, each writing a video-only segment: `mem-guard --wait --max 1400M -- python3 -I render.py <sid>`.
- Then the soundtrack as its own step (`--max 900M`), then concat with `-f concat -c:v copy`, and mux audio last. `examples/gpt-image-2.6/build_all.sh` does all of this.
- Never run two heavy jobs at once. Exit 137 = job too heavy, make it lighter; don't raise the cap.
- Before the full run, do a 3–5 s trial (`--preview 4`) and check max RSS with `/usr/bin/time -v`.

## Encoder (frames piped from PIL)

```
ffmpeg -v error -y -threads 1 -f rawvideo -pix_fmt rgb24 -s 1080x1920 -r 30 -i - \
  -threads 2 -filter_threads 1 -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -x264-params threads=2:rc-lookahead=10:sync-lookahead=0 seg/<sid>.mp4
```

- Write one frame at a time (`np.asarray(img, dtype=np.uint8).tobytes()`). Never keep a list of frames.
- Keep `lru_cache` on full-size images bounded to single digits; text sprites can use ~40.
- **No per-frame random grain.** It defeats compression: 324 MB instead of 20 MB.

## Final mux

```
ffmpeg -v error -y -f concat -safe 0 -i build/concat.txt -i build/audio_mix.wav -threads 2 \
  -map 0:v -map 1:a -af loudnorm=I=-14:TP=-1.5:LRA=7 -c:v copy -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -shortest -movflags +faststart out.mp4
```

Single-pass loudnorm lands around -16 LUFS, peak about -3 dBFS — fine for short-video platforms. Measure with `ffmpeg -af ebur128=peak=true -f null -`.

## The voice is the clock

- `scene_dur = ceil((vo_len + 0.15 + 0.35 [+2.0 on the last scene]) / beat) * beat` — cuts land on the music's beat grid (120 BPM → 0.5 s).
- `cue(sid, "关键词")` returns when that word is spoken, from the TTS word timestamps plus the 0.15 s VO offset. Time every pop-in, callout and counter to the word that names it, not to guessed seconds.
- Captions: built from the TTS sentences (skip the trailing summary entry that has no `words`); split at ，。；：？！ and merge clauses up to 16 characters; place at y≈1690 with a soft shadow; color keywords to match the on-screen palette.
- Keep subjects out of the caption band: main image in the top ~1600 px, or use a contain-canvas.

## The keynote look

- Black background, very large Noto Sans CJK Black type, full-bleed images with slow push-ins (`cam(im, focus, zoom)` cover-crop).
- A 3–4 s hook: montage of the best images on 0.25 s ticks, a white flash, a big gradient title slammed in on an impact.
- Kinetic counting numbers, verdict pills ("✓ 排版完整"), callout lines pointing at features.
- A 0.3 s punch-in at each scene start; a 5 px progress bar along the top.
- One color per concept, used in both captions and on-screen type.

## Sound (audio.py)

- Original score synthesized in numpy (Am–F–C–G, 120 BPM): kick and clap, hats, saw bass in 8ths, pluck 16ths, a pad, sidechain on the kick. The groove runs from the end of the hook to the CTA; the outro is pad only.
- SFX: riser plus ticks under the montage, impact on the title, a whoosh 0.3 s before each cut, a pop at each cue word, a swipe on before/after wipes.
- VO normalized to about -15 dBFS RMS; music ducked ~55 % under the VO; soft-limit the bed with `0.55*tanh(x/0.55)` and leave the VO untouched.

## QA before saying done

- Render stills (`--still t`) at every cue and look at them: text overlapping image text, crops cutting titles, callouts colliding with captions.
- Transcribe the final VO with faster-whisper `small` int8 and compare it with the script.
- Report what was measured (duration, size, LUFS, peak) separately from what was only looked at. Never claim the cut was watched or heard.
