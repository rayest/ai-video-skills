#!/usr/bin/env python3
"""Doubao TTS 2.0 (new console, X-Api-Key only) with word timestamps.

usage: python3 -I tts_doubao.py <script.json> <out_dir> [scene_id ...] [--rate 8] [--dry-run]
script.json: {"scenes": [{"id": "s01", "vo": "..."}]}
Writes <out_dir>/<id>.mp3 and <id>.json (sentences with words[{word,startTime,endTime}]).
The last sentence object is a summary WITHOUT "words" -- skip entries lacking words when using timings.
env (or .env, see load_env): DOUBAO_API_KEY, DOUBAO_VOICE_ID (default zh_male_dayi_uranus_bigtts)
"""
import base64, json, os, sys, uuid, urllib.request, urllib.error
from pathlib import Path

URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


def load_env():
    """Settings come from the environment first, then from a .env file:
    $AI_VIDEO_ENV if set, else ./.env in the current directory."""
    d = {}
    p = Path(os.environ.get("AI_VIDEO_ENV", ".env"))
    if p.is_file():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip("'\"")
    d.update({k: v for k, v in os.environ.items() if k in d or k.startswith(("DOUBAO_", "IMAGE_API_"))})
    return d


def synth(text, key, speaker, rate, out_mp3, out_json):
    body = {"user": {"uid": "ai-video-skills"}, "namespace": "BidirectionalTTS",
            "req_params": {"text": text, "speaker": speaker,
                           "audio_params": {"format": "mp3", "sample_rate": 24000, "speech_rate": rate,
                                            "enable_subtitle": True}}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "X-Api-Key": key, "X-Api-Resource-Id": "seed-tts-2.0", "X-Api-Request-Id": str(uuid.uuid4()),
        "Content-Type": "application/json"})
    audio, sentences = bytearray(), []
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            logid = r.headers.get("X-Tt-Logid")
            for raw in r:
                raw = raw.strip()
                if not raw:
                    continue
                msg = json.loads(raw)
                code = msg.get("code", 0)
                if code not in (0, 20000000):
                    raise SystemExit(f"TTS error {code}: {msg.get('message')} logid={logid}")
                if msg.get("data"):
                    audio += base64.b64decode(msg["data"])
                if msg.get("sentence"):
                    sentences.append(msg["sentence"])
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read()[:500].decode(errors='replace')}")
    out_mp3.write_bytes(audio)
    out_json.write_text(json.dumps(sentences, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    args = sys.argv[1:]
    rate, dry = 8, "--dry-run" in args
    if "--rate" in args:
        i = args.index("--rate"); rate = int(args[i + 1]); del args[i:i + 2]
    args = [a for a in args if a != "--dry-run"]
    if len(args) < 2:
        sys.exit(__doc__)
    scenes = json.loads(Path(args[0]).read_text())["scenes"]
    out, want = Path(args[1]), set(args[2:])
    todo = [s for s in scenes if not want or s["id"] in want]
    n = sum(len(s["vo"]) for s in todo)
    print(f"{len(todo)} lines, {n} chars, ~{n / 6.0:.0f}s at rate {rate}")
    if dry:
        sys.exit(0)
    e = load_env()
    key, speaker = e.get("DOUBAO_API_KEY"), e.get("DOUBAO_VOICE_ID") or "zh_male_dayi_uranus_bigtts"
    if not key:
        sys.exit("set DOUBAO_API_KEY (environment or .env)")
    out.mkdir(parents=True, exist_ok=True)
    for s in todo:
        synth(s["vo"], key, speaker, rate, out / f"{s['id']}.mp3", out / f"{s['id']}.json")
        print("ok", s["id"], flush=True)
