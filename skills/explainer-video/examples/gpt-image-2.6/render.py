#!/usr/bin/env python3
"""Keynote-style renderer (style A) for the GPT-Image-2.6 explainer.

Usage: video-python render.py <scene_id> [--still T] [--preview SECONDS]
Scenes: s00 (hook, no VO) + s01..s10 from script.json. Durations are quantized to the 120 BPM beat grid.
Visual cues are derived from the voiceover word timestamps (cue()), so visuals land on the spoken word.
Frames are composed one at a time and piped to ffmpeg (never held in a list).
"""
import json, math, subprocess, sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
B = HERE / "build"
W, H, FPS = 1080, 1920, 30
BPM = 120
BEAT = 60 / BPM
VO_OFF = 0.15
HOOK = 3.5

CJK_K = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
CJK_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_M = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

WHITE = (255, 255, 255)
GREY = (150, 150, 158)
DGREY = (90, 90, 98)
ORANGE = (255, 128, 40)
PURPLE = (160, 110, 255)
GREEN = (64, 214, 120)
AMBER = (255, 190, 40)
BLACK = (0, 0, 0)

SCRIPT = json.loads((HERE / "script.json").read_text())["scenes"]
SCENES = ["s00"] + [s["id"] for s in SCRIPT]


# ---------------- timing ----------------
def vo_dur(sid):
    p = B / "vo" / f"{sid}.mp3"
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout
    return float(out)


def scene_dur(sid):
    if sid == "s00":
        return HOOK
    d = vo_dur(sid) + VO_OFF + 0.35 + (2.0 if sid == SCENES[-1] else 0)
    return math.ceil(d / BEAT) * BEAT


@lru_cache(maxsize=16)
def charmap(sid):
    """[(char, start_time)] over the VO text without spaces."""
    out = []
    for s in json.loads((B / "vo" / f"{sid}.json").read_text()):
        for w in s.get("words") or []:
            for ch in w["word"].replace(" ", ""):
                out.append((ch, w["startTime"]))
    return out


def cue(sid, key, default=0.0):
    cm = charmap(sid)
    txt = "".join(c for c, _ in cm)
    i = txt.find(key.replace(" ", ""))
    return cm[i][1] + VO_OFF if i >= 0 else default


# ---------------- primitives ----------------
@lru_cache(maxsize=40)
def font(path, size):
    return ImageFont.truetype(path, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def ease_io(p):
    p = clamp(p)
    return p * p * (3 - 2 * p)


def back(p, s=1.6):
    p = clamp(p) - 1
    return 1 + p * p * ((s + 1) * p + s)


def prog(t, start, dur=0.4):
    return ease((t - start) / dur)


@lru_cache(maxsize=12)
def src(name):
    p = A / name if (A / name).exists() else B / name
    return Image.open(p).convert("RGB")


def cam(im, focus, zoom, out=(W, H)):
    """Cover-crop `im` to out-aspect around focus (src px) at zoom (>=1), resized to out."""
    w, h = im.size
    ar = out[0] / out[1]
    if w / h > ar:
        bh, bw = h, h * ar
    else:
        bw, bh = w, w / ar
    bw, bh = bw / zoom, bh / zoom
    cx = clamp(focus[0], bw / 2, w - bw / 2)
    cy = clamp(focus[1], bh / 2, h - bh / 2)
    box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    return im.resize(out, Image.BILINEAR, box=box), box


def lerp(a, b, p):
    return a + (b - a) * p


def lerp_box(a, b, p):
    return tuple(lerp(x, y, p) for x, y in zip(a, b))


def crop_to(im, box, out):
    return im.resize(out, Image.BILINEAR, box=box)


def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def comp(frame, lay, alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    frame.paste(lay, (0, 0), lay)


def tw(s, size, f=CJK_K):
    return font(f, size).getlength(s)


@lru_cache(maxsize=24)
def text_sprite(s, size, color, f=CJK_K, spacing=0):
    fnt = font(f, size)
    if spacing:
        w = int(sum(fnt.getlength(c) for c in s) + spacing * (len(s) - 1)) + 8
    else:
        w = int(fnt.getlength(s)) + 8
    h = int(size * 1.45)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if spacing:
        x = 0
        for c in s:
            d.text((x, 0), c, font=fnt, fill=color)
            x += fnt.getlength(c) + spacing
    else:
        d.text((0, 0), s, font=fnt, fill=color)
    return im


@lru_cache(maxsize=6)
def gradient_text(s, size, c1=ORANGE, c2=PURPLE, f=CJK_K):
    m = text_sprite(s, size, WHITE, f).getchannel("A")
    g = np.zeros((m.height, m.width, 3), np.uint8)
    xs = np.linspace(0, 1, m.width)[None, :, None]
    g[:] = (np.array(c1) * (1 - xs) + np.array(c2) * xs).astype(np.uint8)
    im = Image.fromarray(g).convert("RGBA")
    im.putalpha(m)
    return im


def put(frame, sp, x, y, alpha=1.0, anchor="l", scale=1.0):
    if alpha <= 0:
        return
    if scale != 1.0:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BILINEAR)
    if anchor == "c":
        x -= sp.width / 2
    elif anchor == "r":
        x -= sp.width
    if alpha < 1:
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * alpha)))
    frame.paste(sp, (int(x), int(y)), sp)


def ptext(frame, s, size, x, y, color=WHITE, f=CJK_K, alpha=1.0, anchor="l", slide=0.0, spacing=0):
    put(frame, text_sprite(s, size, color, f, spacing), x, y + slide, alpha, anchor)


def pill(frame, s, size, x, y, fg, bg, alpha=1.0, anchor="l", f=CJK_B):
    if alpha <= 0:
        return
    w = tw(s, size, f) + size * 1.1
    h = size * 1.9
    if anchor == "c":
        x -= w / 2
    elif anchor == "r":
        x -= w
    lay = layer()
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((x, y, x + w, y + h), h / 2, fill=bg)
    d.text((x + size * 0.55, y + size * 0.3), s, font=font(f, size), fill=fg)
    comp(frame, lay, alpha)


@lru_cache(maxsize=1)
def bottom_grad():
    g = np.zeros((H, W, 4), np.uint8)
    ys = np.clip((np.arange(H) - 1250) / 670, 0, 1) ** 1.4
    g[..., 3] = (ys * 235)[:, None].astype(np.uint8)
    return Image.fromarray(g, "RGBA")


@lru_cache(maxsize=1)
def top_grad():
    g = np.zeros((H, W, 4), np.uint8)
    ys = np.clip((420 - np.arange(H)) / 420, 0, 1) ** 1.6
    g[..., 3] = (ys * 200)[:, None].astype(np.uint8)
    return Image.fromarray(g, "RGBA")


@lru_cache(maxsize=4)
def grain(i):
    rng = np.random.default_rng(i)
    return rng.normal(0, 5.5, (H, W, 1)).astype(np.int16)


# ---------------- captions ----------------
KEYS = [("Sunburst", PURPLE), ("Flare", ORANGE), ("Images 2.6", WHITE), ("SVG", ORANGE), ("complexity", ORANGE),
        ("Arena", PURPLE)]


def caption_chunks(sid):
    if sid == "s00":
        return []
    chunks = []
    for si, s in enumerate(json.loads((B / "vo" / f"{sid}.json").read_text())):
        words = s.get("words") or []
        if not words:
            continue
        times = []
        for w in words:
            times += [w["startTime"]] * len(w["word"].replace(" ", ""))
        clauses, cur, ci, cs = [], "", 0, None
        for ch in s["text"]:
            if ch != " ":
                if cs is None:
                    cs = times[min(ci, len(times) - 1)]
                ci += 1
            cur += ch
            if ch in "，。；：？！":
                clauses.append([cs, cur.strip()]); cur, cs = "", None
        if cur.strip():
            clauses.append([cs, cur.strip()])
        for st, c in clauses:
            if chunks and chunks[-1][2] == si and len(chunks[-1][1]) + len(c) <= 16:
                chunks[-1][1] += c
            else:
                chunks.append([st + VO_OFF, c, si])
    return [(st, c) for st, c, _ in chunks]


@lru_cache(maxsize=10)
def caption_sprite(s):
    s = s.rstrip("，。；：、")
    size = 54
    while tw(s, size, CJK_B) > W - 140 and size > 36:
        size -= 2
    fnt = font(CJK_B, size)
    # split into colored runs
    runs, i = [], 0
    while i < len(s):
        for k, col in KEYS:
            if s.startswith(k, i):
                runs.append((k, col)); i += len(k); break
        else:
            runs.append((s[i], WHITE)); i += 1
    w = int(sum(fnt.getlength(r) for r, _ in runs)) + 20
    h = int(size * 1.6)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("L", (w, h), 0)
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    x = 10
    for r, col in runs:
        ds.text((x, 8), r, font=fnt, fill=200)
        d.text((x, 4), r, font=fnt, fill=col)
        x += fnt.getlength(r)
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste((0, 0, 0), (0, 0), sh)
    out.alpha_composite(im)
    return out


def captions(frame, chunks, t):
    cur, st0 = None, 0
    for st, s in chunks:
        if t >= st - 0.04:
            cur, st0 = s, st
    if cur:
        sp = caption_sprite(cur)
        p = ease((t - st0) / 0.18)
        put(frame, sp, W / 2, 1690 + (1 - p) * 14, alpha=0.4 + 0.6 * p, anchor="c")


# ---------------- scenes ----------------
D_SAFE = (205, 330, 883, 1536)   # crop of the rainy-street image without the store signage


def s00(f, t, D):
    order = ["A_poster.png", "B_product_sunburst.png", "D_mascot_scene.png", "G_infographic.png",
             "C_mascot.png", "F_after.png", "B_product_flare.png", "H_logo.png"]
    focus = {"A_poster.png": (512, 300), "G_infographic.png": (512, 520), "F_after.png": (336, 520),
             "C_mascot.png": (512, 520), "H_logo.png": (627, 627), "D_mascot_scene.png": None}
    if t < 2.0:
        k = int(t / 0.25)
        lt = (t - k * 0.25) / 0.25
        name = order[k]
        im = src(name)
        if name == "D_mascot_scene.png":
            im = im.crop(D_SAFE)
        fc = focus.get(name) or (im.width / 2, im.height / 2)
        fr, _ = cam(im, fc, 1.18 - 0.12 * lt)
        f.paste(fr)
        return
    lt = t - 2.0
    s = 1.0 + 0.55 * (1 - back(lt / 0.45, 1.2))
    g = gradient_text("2.6", 420, f=CJK_K)
    put(f, g, W / 2, 700 - (s - 1) * 200, anchor="c", scale=s, alpha=prog(lt, 0, 0.15))
    ptext(f, "GPT  IMAGE", 54, W / 2, 610, WHITE, CJK_B, prog(lt, 0.25), "c", (1 - prog(lt, 0.25)) * 20, spacing=10)
    ptext(f, "OpenAI · 2026.11.04", 40, W / 2, 1290, GREY, CJK_M, prog(lt, 0.5), "c", (1 - prog(lt, 0.5)) * 20)
    flash = clamp(1 - lt / 0.12)
    if flash > 0:
        f.paste(Image.blend(f, Image.new("RGB", (W, H), WHITE), flash))


def s01(f, t, D):
    cv = contain_canvas("A_poster.png", 0)
    z = 1.0 + 0.04 * clamp(t / D)
    fr, _ = cam(cv, (540, 810), z, out=(W, 1620))
    f.paste(fr)
    c2 = cue("s01", "中文一个字", 5.3)
    pill(f, "✓  中文零错字", 44, W / 2, 560, (5, 30, 14), GREEN, prog(t, c2), "c")


def s02(f, t, D):
    c_chat = cue("s02", "这次", 0.2)
    c_api = cue("s02", "API", 2.2)
    c_fl = cue("s02", "Flare", 4.0)
    c_sun = cue("s02", "Sunburst", 4.8)
    c_off = cue("s02", "官方说", 5.6)
    a = prog(t, c_chat)
    ptext(f, "ChatGPT · Codex", 64, 80, 260, WHITE, CJK_K, a, slide=(1 - a) * 30)
    ptext(f, "全部订阅档位 同步升级", 38, 80, 360, GREY, CJK_M, prog(t, c_chat + 0.25))
    a = prog(t, c_api)
    ptext(f, "API 新模型", 38, 80, 520, GREY, CJK_B, a)
    for i, (name, col, c) in enumerate([("Flare", ORANGE, c_fl), ("Sunburst", PURPLE, c_sun)]):
        a = prog(t, c, 0.35)
        put(f, text_sprite(name, 170, col, CJK_K), 72 - (1 - a) * 80, 570 + i * 230, a)
        ptext(f, f"gpt-image-2.6-{name.lower()}", 30, 84, 790 + i * 230 - 0, DGREY, MONO, a)
    a = prog(t, c_off, 0.3)
    n = int(round(50 * ease((t - c_off) / 0.9))) if t > c_off else 0
    put(f, gradient_text(f"+{n}%", 250), 70, 1100, a)
    ptext(f, "速度 · 官方称 · 相比 GPT-Image-2.5", 36, 84, 1470, GREY, CJK_M, prog(t, c_off + 0.4))


@lru_cache(maxsize=2)
def contain_canvas(name, y0=150, bg=BLACK, width=W):
    im = src(name)
    h = round(im.height * width / im.width)
    c = Image.new("RGB", (W, H), bg)
    c.paste(im.resize((width, h), Image.LANCZOS), ((W - width) // 2, y0))
    return c


def s03(f, t, D):
    cv = contain_canvas("G_infographic.png", 170)
    c_fl = cue("s03", "Flare", 0.6)
    c_sun = cue("s03", "Sunburst", 3.5)
    p1 = ease_io((t - c_fl) / 0.8)
    p2 = ease_io((t - c_sun) / 0.8)
    z = 1.0 + 0.75 * p1
    fx = lerp(lerp(540, 285, p1), 800, p2)
    fy = lerp(960, 1030, p1)
    fr, _ = cam(cv, (fx, fy), z, out=(W, 1560))
    f.paste(fr)


def s04(f, t, D):
    hh = 958
    c_ok = cue("s04", "字都写对", 2.9)
    c_fl = cue("s04", "但Flare", 3.8)
    c_sun = cue("s04", "Sunburst的排版", 6.0)
    zp = ease_io((t - c_ok + 0.1) / 0.9)
    specs = [("B_product_flare.png", (0, 306, 1024, 1214), (285, 670, 805, 1131), "Flare", ORANGE),
             ("B_product_sunburst.png", (0, 306, 1024, 1214), (340, 600, 880, 1079), "Sunburst", PURPLE)]
    for i, (name, wide, lab, title, col) in enumerate(specs):
        a = prog(t, 0.1 + 0.25 * i, 0.5)
        box = lerp_box(wide, lab, zp)
        half = crop_to(src(name), box, (W, hh))
        y = i * (hh + 4)
        f.paste(half, (int((1 - a) * (-W if i == 0 else W)), y))
        pill(f, title, 40, 40, y + 36 if i == 0 else y + 36, (20, 10, 0), col, a)
    ImageDraw.Draw(f).rectangle((0, hh, W, hh + 4), fill=BLACK)
    pill(f, "标签断成两行", 38, W - 40, 36, (40, 26, 0), AMBER, prog(t, c_fl + 0.3), "r")
    pill(f, "✓  排版完整", 38, W - 40, hh + 40, (5, 30, 14), GREEN, prog(t, c_sun), "r")


def s05(f, t, D):
    c_ref = cue("s05", "再用参考图", 3.4)
    if t < c_ref:
        f.paste(WHITE, (0, 0, W, H))
        im = src("C_mascot.png")
        z = 1.0 + 0.05 * t / c_ref
        s = int(W * z)
        f.paste(im.resize((s, s), Image.BILINEAR), (int((W - s) / 2), int(380 - (s - W) / 2)))
        ptext(f, "① 设定图", 44, 70, 160, (20, 20, 24), CJK_K, prog(t, 0.2))
        ptext(f, "原创角色「小焰」", 34, 70, 230, (110, 110, 118), CJK_M, prog(t, 0.4))
        return
    lt = t - c_ref
    im = src("D_mascot_scene.png").crop(D_SAFE)
    z = 1.0 + 0.04 * lt / max(0.1, D - c_ref)
    fr, box = cam(im, (im.width / 2, im.height / 2), z)
    f.paste(fr)
    f.paste(top_grad(), (0, 0), top_grad())
    ptext(f, "② 参考图 → 新场景", 48, 70, 1520, WHITE, CJK_K, prog(lt, 0.0, 0.3))
    sx = W / (box[2] - box[0])

    def m(px, py):  # source (full D image) -> frame
        return ((px - D_SAFE[0] - box[0]) * sx, (py - D_SAFE[1] - box[1]) * sx)

    callouts = [("耳朵", (390, 545), "透明蓝耳尖", -1), ("眼睛", (640, 650), "青色发光眼", 1),
                ("火焰", (548, 850), "胸前火焰标志", -1), ("全都保住", (820, 930), "分节金属尾巴", 1)]
    d = None
    for key, pt, label, side in callouts:
        c = cue("s05", key, 6.0)
        a = prog(t, c, 0.3)
        if a <= 0:
            continue
        x, y = m(*pt)
        lay = layer()
        d = ImageDraw.Draw(lay)
        r = 16 + 10 * (1 - a)
        d.ellipse((x - r, y - r, x + r, y + r), outline=WHITE, width=5)
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=WHITE)
        lx = x + side * 70 * a
        ex = lx + side * 40
        d.line((x + side * r, y, ex, y), fill=WHITE, width=4)
        fnt = font(CJK_K, 40)
        tw_ = fnt.getlength(label)
        bx0 = ex if side > 0 else ex - tw_ - 44
        bx0 = clamp(bx0, 20, W - tw_ - 64)
        d.rounded_rectangle((bx0, y - 34, bx0 + tw_ + 44, y + 34), 34, fill=(0, 0, 0, 190))
        d.text((bx0 + 22, y - 28), label, font=fnt, fill=WHITE)
        comp(f, lay, a)


_gif = []


def gif_frames():
    if not _gif:
        im = Image.open(A / "E_mascot_gif.gif")
        i = 0
        while True:
            try:
                im.seek(i)
            except EOFError:
                break
            _gif.append(im.convert("RGB").resize((W, W), Image.LANCZOS))  # 12 frames, ~3.5 MB each
            i += 1
    return _gif


def s06(f, t, D):
    f.paste(WHITE, (0, 0, W, H))
    fr = gif_frames()
    f.paste(fr[int(t * 1000 / 150) % len(fr)], (0, 300))
    ptext(f, "GIF", 120, 70, 110, (20, 20, 24), CJK_K, prog(t, 0.1))
    ptext(f, "动图生成", 44, 300, 170, (110, 110, 118), CJK_B, prog(t, 0.3))
    c = cue("s06", "十二帧", 3.0)
    a = prog(t, c)
    ptext(f, "12 帧", 110, 70, 1390, (20, 20, 24), CJK_K, a, slide=(1 - a) * 20)
    ptext(f, "× 150 ms", 60, 400, 1425, ORANGE, CJK_K, prog(t, c + 0.25))


def s07(f, t, D):
    before = contain_canvas("F_markup_view.png", 260)
    after = src("F_after.png").resize((W, 1620), Image.LANCZOS) if not hasattr(s07, "_a") else s07._a
    s07._a = after
    c_mark = cue("s07", "圈出标签", 2.6)
    c_do = cue("s07", "让它换成", 3.4)
    c_keep = cue("s07", "瓶子", 5.7)
    canvas = before.copy()
    wp = ease_io((t - c_do) / 1.3)
    cut = int(W * wp)
    if cut > 0:
        canvas.paste(after.crop((0, 0, cut, 1620)), (0, 260))
    if 0 < wp < 1:
        ImageDraw.Draw(canvas).rectangle((cut - 3, 260, cut + 3, 1880), fill=WHITE)
    zp = ease_io((t - c_keep) / 1.0)
    zp2 = ease_io((t - c_mark) / 0.8) * (1 - zp)
    z = 1.0 + 0.35 * zp2
    fr, _ = cam(canvas, (lerp(540, 610, zp2), lerp(1070, 1140, zp2)), z)
    f.paste(fr)
    f.paste(top_grad(), (0, 0), top_grad())
    lab = "AFTER" if wp >= 1 else "BEFORE"
    ptext(f, lab, 40, W - 70, 120, WHITE, CJK_K, prog(t, 0.1), "r", spacing=6)
    ptext(f, "标注编辑", 64, 70, 100, WHITE, CJK_K, prog(t, 0.1))
    instr = "“标签改墨绿色，改名「晨光 · 冷萃」”"
    k = int(clamp((t - c_mark) / 1.2) * len(instr))
    if k:
        ptext(f, instr[:k], 34, 72, 190, GREY, CJK_M)


CODE = [('client.images.generate(', WHITE), ('  model="gpt-image-2.6-sunburst",', WHITE),
        ('  prompt="…",', DGREY), ('  complexity="low",', ORANGE), ('  output_format="svg",', ORANGE), (')', WHITE)]


def s08(f, t, D):
    c_cx = cue("s08", "complexity", 0.6)
    c_svg = cue("s08", "SVG", 3.3)
    c_but = cue("s08", "不过", 5.6)
    up = ease_io((t - c_svg + 0.2) / 0.7)
    lay = layer()
    d = ImageDraw.Draw(lay)
    y0 = lerp(420, 150, up)
    shown = int((t - 0.1) * 55)
    for i, (line, col) in enumerate(CODE):
        s = line[:max(0, shown)]
        shown -= len(line)
        y = y0 + i * 74
        if "complexity" in line and t > c_cx:
            hp = prog(t, c_cx, 0.3)
            d.rounded_rectangle((60, y - 8, 60 + 960 * hp, y + 62), 12, fill=(255, 128, 40, 50))
        d.text((80, y), s, font=font(MONO, 44), fill=col)
    comp(f, lay, 1.0 - 0.55 * up)
    if up > 0:
        a = prog(t, c_svg, 0.5)
        ptext(f, "SVG", 330, W / 2, 640, (34, 34, 40), CJK_K, a, "c")
        logo = src("H_logo.png")
        s = int(620 * lerp(0.7, 1.0, back((t - c_svg) / 0.5, 1.3)))
        if a > 0:
            lg = logo.resize((s, s), Image.LANCZOS)
            m = Image.new("L", (s, s), 0)
            ImageDraw.Draw(m).ellipse((s * 0.04, s * 0.04, s * 0.96, s * 0.96), fill=int(255 * a))
            f.paste(lg, (int(W / 2 - s / 2), int(1010 - s / 2)), m)
        ptext(f, "矢量输出 · 约 1 KB", 40, W / 2, 1360, GREY, CJK_B, prog(t, c_svg + 0.4), "c")
        pill(f, "造型偏抽象", 36, W / 2, 1440, (40, 26, 0), AMBER, prog(t, c_but), "c")


def s09(f, t, D):
    c_q = cue("s09", "质量越高", 4.5)
    c_ar = cue("s09", "第三方", 7.4)
    a = prog(t, 0.15, 0.3)
    n = int(round(30 * ease((t - 0.15) / 0.9)))
    put(f, gradient_text(f"${n}", 260, WHITE, (200, 200, 210)), 70, 200, a)
    ptext(f, "每百万图像输出 tokens · 与 2.5 同价", 38, 84, 560, GREY, CJK_M, prog(t, 0.6))
    a = prog(t, c_q)
    ptext(f, "按 token 计费", 84, 70, 720, ORANGE, CJK_K, a, slide=(1 - a) * 20)
    ptext(f, "质量越高、尺寸越大，用量越多", 38, 84, 850, GREY, CJK_M, prog(t, c_q + 0.3))
    a = prog(t, c_ar, 0.3)
    put(f, gradient_text("#2", 260, PURPLE, (230, 120, 255)), 70, 1010, a, scale=lerp(1.25, 1.0, a))
    ptext(f, "Arena 文生图初步榜 · Sunburst", 40, 84, 1380, WHITE, CJK_B, prog(t, c_ar + 0.3))
    pill(f, "第三方 · 初步", 30, 450, 1060, (40, 26, 0), AMBER, prog(t, c_ar + 0.5))
    ptext(f, "社区反馈：中低质量档 token 用量明显增加", 30, 84, 1450, DGREY, CJK_M, prog(t, c_ar + 1.2))


def s10(f, t, D):
    c_sun = cue("s10", "精修", 2.6)
    c_q = cue("s10", "你最想", 5.0)
    dim = 1 - 0.75 * prog(t, c_q, 0.5)
    a = prog(t, 0.2, 0.5)
    put(f, text_sprite("Flare", 200, ORANGE, CJK_K), 70 - (1 - a) * 80, 230, a * dim)
    ptext(f, "草稿 · 海报 · 商品图", 50, 84, 500, WHITE, CJK_B, a * dim)
    a = prog(t, c_sun, 0.5)
    put(f, text_sprite("Sunburst", 200, PURPLE, CJK_K), 70 + (1 - a) * 80, 680, a * dim)
    ptext(f, "精修 · 角色 · 动图", 50, 84, 950, WHITE, CJK_B, a * dim)
    b = prog(t, c_q, 0.5)
    ptext(f, "你最想先试哪个？", 92, W / 2, 1180, WHITE, CJK_K, b, "c", (1 - b) * 30)
    ptext(f, "评论区见", 50, W / 2, 1330, ORANGE, CJK_B, prog(t, c_q + 0.4), "c")
    ptext(f, "资料：OpenAI 发布页 · API 文档 · 开发者社区 · Arena", 26, W / 2, 1480, DGREY, CJK_M,
          prog(t, c_q + 0.8), "c")


FN = {k: globals()[k] for k in SCENES}


def compose(sid, t, D, g0, total, chunks, fi):
    f = Image.new("RGB", (W, H), BLACK)
    FN[sid](f, t, D)
    if sid != "s00":
        f.paste(bottom_grad(), (0, 0), bottom_grad())
        captions(f, chunks, t)
        # punch-in at scene start
        pz = 1 - ease(t / 0.3)
        if pz > 0:
            s = 1 + 0.035 * pz
            f = f.resize((int(W * s), int(H * s)), Image.BILINEAR).crop(
                (int((W * s - W) / 2), int((H * s - H) / 2), int((W * s - W) / 2) + W, int((H * s - H) / 2) + H))
    d = ImageDraw.Draw(f)
    d.rectangle((0, 0, int(W * (g0 + t) / total), 5), fill=(255, 255, 255))
    return np.asarray(f, dtype=np.uint8)


def timeline():
    durs = {s: scene_dur(s) for s in SCENES}
    starts, g = {}, 0.0
    for s in SCENES:
        starts[s] = g
        g += durs[s]
    return durs, starts, g


if __name__ == "__main__":
    sid = sys.argv[1]
    durs, starts, total = timeline()
    D = durs[sid]
    chunks = caption_chunks(sid)
    if "--still" in sys.argv:
        t = float(sys.argv[sys.argv.index("--still") + 1])
        Image.fromarray(compose(sid, t, D, starts[sid], total, chunks, 0)).save(B / f"v2_{sid}_{t:.1f}.png")
        sys.exit(0)
    n = int(round(D * FPS))
    if "--preview" in sys.argv:
        n = min(n, int(float(sys.argv[sys.argv.index("--preview") + 1]) * FPS))
    out = B / "seg" / f"{sid}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-threads", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-threads", "2", "-filter_threads", "1", "-c:v", "libx264", "-preset", "medium",
        "-crf", "19", "-pix_fmt", "yuv420p", "-x264-params", "threads=2:rc-lookahead=10:sync-lookahead=0",
        str(out)], stdin=subprocess.PIPE)
    for i in range(n):
        enc.stdin.write(compose(sid, i / FPS, D, starts[sid], total, chunks, i).tobytes())
    enc.stdin.close()
    sys.exit(enc.wait())
