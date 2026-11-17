#!/usr/bin/env python3
"""Generate one image/GIF/SVG through an async image-task API (the ToAPIs-style
/v1/images/generations + polling protocol). Network only, no heavy work.

usage: python3 -I gen_image.py <out_path_without_ext> --prompt "..." [--model sunburst|flare|<full id>]
         [--size 2:3|1:1|3:2|auto] [--quality low|medium|high] [--ref img.png ...] [--markup layer.png]
         [--gif FRAMES:MS] [--svg]
Saves <out>.<ext> and appends a JSON line (usage/billing/params) to <out dir>/results.jsonl.
Billing/timing in results.jsonl is for us only -- never put it in a video.
env (or .env, see load_env): IMAGE_API_KEY, IMAGE_API_BASE
"""
import argparse, json, mimetypes, os, random, sys, time, uuid, urllib.request, urllib.error
from pathlib import Path

BASE = None
MODELS = {"flare": "gpt-image-2.6-flare-official", "sunburst": "gpt-image-2.6-sunburst-official"}
UA = {"User-Agent": "ai-video-skills/1.0"}
KEY = None


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


def req(method, path, body=None, raw=None):
    h = {"Authorization": f"Bearer {KEY}", **UA}
    data = None
    if body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    if raw is not None:
        data, h["Content-Type"] = raw
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers=h, method=method),
                                    timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} {path}: {e.read()[:800].decode(errors='replace')}")


def upload(path: Path):
    b = uuid.uuid4().hex
    ct = mimetypes.guess_type(path.name)[0] or "image/png"
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ct}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    return req("POST", "/v1/uploads/images", raw=(body, f"multipart/form-data; boundary={b}"))["data"]["url"]


def main():
    global KEY, BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default="sunburst")
    ap.add_argument("--size", default="2:3")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--ref", nargs="*", default=[])
    ap.add_argument("--markup")
    ap.add_argument("--gif", help="FRAMES:MS, e.g. 12:150 (use sunburst + size auto)")
    ap.add_argument("--svg", action="store_true")
    a = ap.parse_args()
    e = load_env()
    KEY, BASE = e.get("IMAGE_API_KEY"), (e.get("IMAGE_API_BASE") or "").rstrip("/")
    if not KEY or not BASE:
        sys.exit("set IMAGE_API_KEY and IMAGE_API_BASE (environment or .env)")
    body = {"model": MODELS.get(a.model, a.model), "prompt": a.prompt, "n": 1, "size": a.size}
    if a.gif:
        fr, ms = a.gif.split(":")
        body.update(output_format="gif", frame_count=int(fr), frame_duration_ms=int(ms))
    elif a.svg:
        body.update(output_format="svg", svg={"model": "gpt-5"})
        body.pop("size")
    else:
        body["quality"] = a.quality
    if a.ref:
        body["image_urls"] = [upload(Path(p)) for p in a.ref]
    if a.markup:
        body["markup_url"] = upload(Path(a.markup))
    tid = req("POST", "/v1/images/generations", body)["id"]
    print(f"submitted {tid} ({body['model']})", flush=True)
    time.sleep(5)
    while True:
        st = req("GET", f"/v1/images/generations/{tid}")
        if st["status"] in ("completed", "failed"):
            break
        time.sleep(6 + random.random() * 3)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rec = {"out": out.name, "task": tid, "status": st["status"], "usage": st.get("usage"),
           "billing": st.get("billing"), "error": st.get("error"),
           "params": {k: v for k, v in body.items() if k not in ("prompt", "image_urls", "markup_url")}}
    if st["status"] == "completed":
        url = st["result"]["data"][0]["url"]
        ext = body.get("output_format") or Path(url.split("?")[0]).suffix.lstrip(".") or "png"
        f = out.with_name(f"{out.name}.{ext}")
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            f.write_bytes(r.read())
        rec["file"] = f.name
        print(f"ok -> {f}")
    else:
        print(f"failed: {st.get('error')}")
    with open(out.parent / "results.jsonl", "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sys.exit(0 if st["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
