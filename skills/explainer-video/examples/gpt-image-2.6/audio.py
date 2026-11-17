#!/usr/bin/env python3
"""Style-A soundtrack: voiceover at scene offsets + original 120 BPM score + synthesized SFX -> build/audio_mix.wav"""
import subprocess, sys, wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render as R  # noqa: E402

SR = 44100
rng = np.random.default_rng(7)


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-threads", "1", "-i", str(path), "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def add(buf, at, sig, gain=1.0):
    i = int(at * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += gain * sig[: j - i]


def env_exp(n, k):
    return np.exp(-np.arange(n) / SR * k)


def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) + 0.15 * rng.standard_normal(n) * np.exp(-t * 200)


def clap():
    n = int(0.25 * SR); t = np.arange(n) / SR
    s = rng.standard_normal(n)
    s = np.convolve(s, [1, -0.9], "same")
    return s * (np.exp(-t * 22) + 0.6 * np.exp(-((t - 0.012) % 0.011) * 400) * (t < 0.035))


def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR); t = np.arange(n) / SR
    s = np.diff(rng.standard_normal(n + 1))
    return s * np.exp(-t * (14 if open_ else 80))


def saw(f, n, harm=7):
    t = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harm + 1))


def whoosh(d=0.45, up=True):
    n = int(d * SR); t = np.arange(n) / SR
    s = rng.standard_normal(n)
    # sweep a one-pole lowpass cutoff
    cut = np.linspace(0.02, 0.35, n) if up else np.linspace(0.35, 0.02, n)
    y = np.zeros(n); acc = 0.0
    for i in range(n):
        acc += cut[i] * (s[i] - acc); y[i] = acc
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5
    return y * e * 3


def pop():
    n = int(0.12 * SR); t = np.arange(n) / SR
    f = 900 + 1400 * np.exp(-t * 60)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38)


def impact():
    n = int(2.2 * SR); t = np.arange(n) / SR
    f = 30 + 90 * np.exp(-t * 6)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    noise = rng.standard_normal(n) * np.exp(-t * 5) * 0.25
    return boom + noise


def riser(d):
    n = int(d * SR); t = np.arange(n) / SR
    f = 200 * (8 ** (t / d))
    return (0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * whoosh(d)[:n]) * (t / d) ** 2


def swipe():
    return whoosh(0.6, up=False)


def score(total, groove_start, groove_end):
    n = int(total * SR)
    mus = np.zeros(n)
    bar = 4 * R.BEAT
    prog = [(45, [57, 60, 64]), (41, [57, 60, 65]), (48, [55, 60, 64]), (43, [55, 59, 62])]
    side = np.ones(n)
    nb = int(total / bar) + 1
    k, c, ho, hc = kick(), clap(), hat(True), hat()
    for b in range(nb):
        b0 = b * bar
        root, chord = prog[b % 4]
        in_groove = groove_start - 1e-6 <= b0 < groove_end
        # pad (whole song)
        L = int(bar * SR)
        t = np.arange(L) / SR
        pad = sum(np.sin(2 * np.pi * midi(x) * t * (1 + d)) for x in chord for d in (-0.002, 0.002))
        pad *= np.minimum(1, t / 0.3) * np.minimum(1, (bar - t) / 0.3)
        add(mus, b0, pad, 0.045)
        if not in_groove:
            continue
        for q in range(4):
            tq = b0 + q * R.BEAT
            add(mus, tq, k, 0.55)
            i = int(tq * SR)
            dk = 1 - 0.65 * np.exp(-np.arange(int(0.3 * SR)) / SR * 9)
            j = min(n, i + len(dk))
            if j > i:
                side[i:j] = np.minimum(side[i:j], dk[: j - i])
            if q in (1, 3):
                add(mus, tq, c, 0.18)
            add(mus, tq + R.BEAT / 2, ho if q == 3 else hc, 0.07 if q == 3 else 0.09)
            for e in range(2):  # bass 8ths
                tb = tq + e * R.BEAT / 2
                L2 = int(R.BEAT / 2 * SR * 0.9)
                bs = saw(midi(root - 12), L2, 6) * env_exp(L2, 7)
                add(mus, tb, bs, 0.09)
            for s16 in range(4):  # pluck 16ths
                tp = tq + s16 * R.BEAT / 4
                note = chord[(q * 4 + s16) % 3] + (12 if s16 % 2 else 0)
                L3 = int(0.18 * SR)
                add(mus, tp, np.sin(2 * np.pi * midi(note + 12) * np.arange(L3) / SR) * env_exp(L3, 22), 0.035)
    return mus * side


def main():
    durs, starts, total = R.timeline()
    n = int(total * SR) + SR
    vo = np.zeros(n)
    for sid in R.SCENES[1:]:
        a = decode(R.B / "vo" / f"{sid}.mp3").astype(np.float64)
        add(vo, starts[sid] + R.VO_OFF, a)
    voiced = np.abs(vo) > 0.01
    vo *= 10 ** (-15 / 20) / np.sqrt(np.mean(vo[voiced] ** 2))

    last = R.SCENES[-1]
    groove_end = starts[last] + R.cue(last, "你最想", 5.0)
    groove_end = round(groove_end / (4 * R.BEAT)) * 4 * R.BEAT
    mus = score(n / SR, R.HOOK, groove_end)
    t = np.arange(n) / SR
    mus *= np.clip(t / 0.5, 0, 1) * np.clip((total - t) / 2.5, 0, 1)

    sfx = np.zeros(n)
    add(sfx, 0.0, riser(2.0), 0.35)
    for k in range(8):
        add(sfx, k * 0.25, pop(), 0.12)
        add(sfx, k * 0.25, kick(), 0.35)
    add(sfx, 2.0, impact(), 0.8)
    for sid in R.SCENES[2:]:
        add(sfx, starts[sid] - 0.3, whoosh(0.45), 0.22)
    S = starts
    ev = [("s01", "中文一个字"), ("s02", "这次"), ("s02", "API"), ("s02", "Flare"), ("s02", "Sunburst"),
          ("s02", "官方说"), ("s04", "Sunburst的排版"), ("s05", "耳朵"), ("s05", "眼睛"), ("s05", "火焰"),
          ("s05", "全都保住"), ("s06", "十二帧"), ("s08", "SVG"), ("s08", "不过"), ("s09", "质量越高"),
          ("s09", "第三方"), ("s10", "精修"), ("s10", "你最想")]
    for sid, key in ev:
        add(sfx, S[sid] + R.cue(sid, key), pop(), 0.16)
    add(sfx, S["s04"] + R.cue("s04", "但Flare") + 0.3, pop(), 0.16)
    add(sfx, S["s05"] + R.cue("s05", "再用参考图") - 0.2, whoosh(0.4), 0.25)
    add(sfx, S["s07"] + R.cue("s07", "让它换成"), swipe(), 0.3)
    add(sfx, S["s09"] + 0.15, pop(), 0.16)

    env = np.convolve(np.abs(vo), np.ones(SR // 10) / (SR // 10), "same")
    duck = 1 - 0.55 * np.clip(env / 0.03, 0, 1)
    duck = np.convolve(duck, np.ones(SR // 5) / (SR // 5), "same")
    bed = 0.75 * mus * duck + 0.8 * sfx
    bed = 0.55 * np.tanh(bed / 0.55)  # soft-limit the bed so VO level is kept
    mix = vo + bed
    peak = np.max(np.abs(mix))
    mix *= min(1.0, 0.95 / peak)
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(R.B / "audio_mix.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print(f"total {total:.2f}s peak {peak:.2f}")


if __name__ == "__main__":
    main()
