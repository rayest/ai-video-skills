"""Generate one MiniMax voiceover clip per line of a promo script.

usage: tts_minimax.py VOICE_DIR [--voice ID] [--model M] [--speed 1.0] [--only id,id] [--dry-run]

VOICE_DIR/script.json is a list of {"id": "...", "text": "..."}.
Writes VOICE_DIR/vo-<id>.mp3 and VOICE_DIR/durations.json ([{"id", "ms"}]), which is what
the timeline is built from. Each call is billed by MiniMax, so --dry-run first and get
the user's go-ahead; --only regenerates single lines instead of the whole script.

Key: $MINIMAX_API_KEY, else the first line of ~/.minimax_key. The key is never printed.
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("voice_dir")
ap.add_argument("--voice", default="Chinese (Mandarin)_Reliable_Executive")
ap.add_argument("--model", default="speech-2.8-hd")
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--url", default="https://api.minimax.cn/v1/t2a_v2")
ap.add_argument("--only", default="", help="comma-separated ids to (re)generate")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

out = pathlib.Path(a.voice_dir)
lines = json.loads(out.joinpath("script.json").read_text())
if a.only:
    wanted = set(a.only.split(","))
    lines = [line for line in lines if line["id"] in wanted]
chars = sum(len(line["text"]) for line in lines)
print(f"{len(lines)} lines, {chars} characters, ~{chars / 4.5:.1f} s of speech at 4.5 chars/s")
if a.dry_run:
    sys.exit(0)

key = os.environ.get("MINIMAX_API_KEY") or pathlib.Path.home().joinpath(".minimax_key").read_text().strip().splitlines()[0]
meta_path = out / "durations.json"
meta = {m["id"]: m for m in json.loads(meta_path.read_text())} if meta_path.exists() else {}
for line in lines:
    payload = {"model": a.model, "text": line["text"], "stream": False,
               "voice_setting": {"voice_id": a.voice, "speed": a.speed, "vol": 1, "pitch": 0},
               "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
               "output_format": "hex"}
    req = urllib.request.Request(a.url, data=json.dumps(payload, ensure_ascii=False).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        body = json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        sys.exit(f"{line['id']}: HTTP {e.code}")
    status = body.get("base_resp", {})
    if status.get("status_code") != 0:
        sys.exit(f"{line['id']}: MiniMax status {status.get('status_code')} {status.get('status_msg')}")
    out.joinpath(f"vo-{line['id']}.mp3").write_bytes(bytes.fromhex(body["data"]["audio"]))
    ms = body.get("extra_info", {}).get("audio_length")
    meta[line["id"]] = {"id": line["id"], "ms": ms}
    print(line["id"], ms, "ms")
order = [json.loads(out.joinpath("script.json").read_text())]
ids = [line["id"] for line in order[0]]
meta_path.write_text(json.dumps([meta[i] for i in ids if i in meta], indent=1, ensure_ascii=False))
