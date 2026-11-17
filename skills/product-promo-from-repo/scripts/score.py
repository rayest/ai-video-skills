"""Original promo score synthesized in code (no samples, no licences).

Sections follow a launch film: hook -> chaos (tense, filtered) -> reveal (music opens)
-> product groove -> build into the payoff -> breakdown under the claim -> logo hit.
The bar grid is anchored so a downbeat lands exactly on --payoff, and the logo hit
lands --logo-beats beats after it.

usage: score.py OUT.wav --total 38.5 --bpm 104 --hook-end 4.6 --reveal 9.8 \
                --build 24.2 --payoff 27.0 --claim 31.6 --logo-beats 13
Needs numpy + scipy.
"""
import argparse
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--total", type=float, required=True, help="film length, s")
ap.add_argument("--bpm", type=float, default=104)
ap.add_argument("--hook-end", type=float, required=True, help="end of hook / start of chaos")
ap.add_argument("--reveal", type=float, required=True, help="brand reveal: music opens")
ap.add_argument("--build", type=float, required=True, help="start of the build into the payoff")
ap.add_argument("--payoff", type=float, required=True, help="biggest moment, lands on a bar downbeat")
ap.add_argument("--claim", type=float, required=True, help="start of the breakdown under the claim")
ap.add_argument("--logo-beats", type=int, required=True, help="beats from payoff to the logo hit")
ap.add_argument("--seed", type=int, default=104)
A = ap.parse_args()

SR = 44100
TOTAL = A.total
BPM = A.bpm
B = 60 / BPM                 # one beat
S = B / 4                    # one sixteenth
BAR = 4 * B
PAYOFF = A.payoff
LOGO = PAYOFF + A.logo_beats * B
T0 = PAYOFF - int(np.ceil(PAYOFF / BAR + 1)) * BAR       # downbeat of bar 0 (negative: the film starts mid-grid)
N = int((TOTAL + 1.5) * SR)
rng = np.random.default_rng(A.seed)

# F major: F – C – Dm – Bb (I V vi IV); chaos uses Dm – Bb° colour
PROG = [(41, [65, 69, 72, 77]), (36, [64, 67, 72, 76]), (38, [62, 65, 69, 74]), (34, [62, 65, 70, 74])]
TENSE = [(38, [62, 65, 68, 74]), (37, [61, 65, 68, 73])]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tt(d):
    return np.arange(int(d * SR)) / SR


def env(n, a=0.004, r=0.04):
    e = np.ones(n)
    na, nr = min(int(a * SR), n), min(int(r * SR), n)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, kind, fs=SR, output="sos"), x)


def noise(d):
    return rng.standard_normal(int(d * SR))


# ---------------------------------------------------------------- instruments
def pluck(m, d=0.35, v=1.0, bright=1.0):
    t = tt(d); f = hz(m)
    x = sum(np.sin(2 * np.pi * f * h * t) * 0.62 ** h * np.exp(-t * (6 + h * 3.5 / bright)) for h in range(1, 9))
    return x * env(len(t), 0.002, 0.03) * 0.28 * v


def bass(m, d, v=1.0):
    t = tt(d); f = hz(m)
    saw = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 7))
    x = filt(saw, "low", 420) + 0.6 * np.sin(2 * np.pi * f * t)
    return x * np.exp(-t * 1.6) * env(len(t), 0.004, 0.05) * 0.42 * v


def pad(ms, d, v=1.0, cut=2200):
    t = tt(d)
    x = sum(np.sin(2 * np.pi * hz(m) * (1 + det) * t + det * 40) for m in ms for det in (-0.003, 0.0, 0.003))
    x = filt(x, "low", cut)
    return x * env(len(t), 0.35, 0.5) * 0.05 * v


def keys(ms, d=0.9, v=1.0):
    t = tt(d)
    x = sum(sum(np.sin(2 * np.pi * hz(m) * h * t) / h ** 1.5 * np.exp(-t * (2.2 + h)) for h in range(1, 5)) for m in ms)
    return x * env(len(t), 0.003, 0.08) * 0.07 * v


def kick(v=1.0):
    t = tt(0.32)
    f = 48 + 110 * np.exp(-t * 32)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.95 * v


def snare(v=1.0):
    t = tt(0.22)
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 26) * 0.4
    nz = filt(noise(0.22), "band", [1600, 7000]) * np.exp(-t * 17) * 0.55
    return (body + nz) * v


def clap(v=1.0):
    t = tt(0.25)
    e = sum(np.exp(-np.clip(t - o, 0, None) * 60) * (t >= o) for o in (0, 0.011, 0.022)) + np.exp(-t * 14) * 0.6
    return filt(noise(0.25), "band", [900, 4500]) * e * 0.32 * v


def hat(v=1.0, d=0.045):
    t = tt(d)
    return filt(noise(d), "high", 7500) * np.exp(-t * 90) * 0.22 * v


def crash(v=1.0):
    t = tt(2.2)
    return filt(noise(2.2), "high", 5000) * np.exp(-t * 2.3) * 0.2 * v


def sub_hit(v=1.0):
    t = tt(1.6)
    f = 36 + 60 * np.exp(-t * 14)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4) * 0.9 * v


# ---------------------------------------------------------------- arranging
buf = np.zeros(N)
verb_send = np.zeros(N)


def put(t0, x, send=0.0):
    i = int(round(t0 * SR))
    if i >= N or i + len(x) <= 0:
        return
    if i < 0:
        x = x[-i:]; i = 0
    j = min(N, i + len(x))
    buf[i:j] += x[: j - i]
    if send:
        verb_send[i:j] += x[: j - i] * send


def bar_time(k):
    return T0 + k * BAR


def bars_in(a, b):
    """bar indices whose downbeat falls in [a, b)"""
    k0 = int(np.ceil((a - T0) / BAR))
    k = k0
    while bar_time(k) < b:
        yield k
        k += 1


def chord_at(k, tense=False):
    seq = TENSE if tense else PROG
    return seq[k % len(seq)]


def groove(k, full=True, hats=True, arp=True, v=1.0):
    t = bar_time(k)
    root, ch = chord_at(k)
    for b in range(4):
        put(t + b * B, kick(0.9 * v))
        if b % 2 == 1:
            put(t + b * B, clap(v) if full else snare(0.6 * v))
    if hats:
        for s in range(16):
            if s % 2 == 1 or full:
                put(t + s * S, hat((0.9 if s % 4 == 2 else 0.5) * v))
    # off-beat bass
    for b in range(4):
        put(t + b * B + 2 * S, bass(root + (12 if b == 3 else 0), B * 0.45, v))
    if arp:
        order = [0, 1, 2, 3, 2, 1, 3, 2]
        for s in range(0, 16, 2):
            put(t + s * S, pluck(ch[order[(s // 2) % 8]] + 12, 0.3, 0.85 * v, bright=1.4), send=0.25)
    put(t, pad(ch, BAR + 0.2, v), send=0.4)


# hook: light groove, no clap yet
for k in bars_in(-BAR, A.hook_end):
    groove(k, full=False, hats=False, arp=True, v=0.5)

# chaos: tense, filtered, stuttering
chaos = np.zeros(N)
saved = buf; buf = chaos
for k in bars_in(A.hook_end - 0.3, A.reveal):
    t = bar_time(k); root, ch = chord_at(k, tense=True)
    for s in (0, 3, 6, 10, 11, 14):
        put(t + s * S, kick(0.6) if s in (0, 6, 10) else hat(0.7))
    for s in range(0, 16, 3):
        put(t + s * S, pluck(ch[s % 4] + 12, 0.18, 0.8, bright=0.7))
    put(t, bass(root, BAR * 0.9, 0.7))
    put(t, pad(ch, BAR + 0.2, 0.9, cut=900))
buf = saved
i0, i1 = int((A.hook_end - 0.05) * SR), int(A.reveal * SR)
seg = filt(chaos[i0:i1], "low", 1400)
# tremolo stutter that speeds up toward the collapse
tt_ = np.arange(len(seg)) / SR
seg *= 0.65 + 0.35 * np.sign(np.sin(2 * np.pi * (4 + 6 * tt_ / tt_[-1]) * tt_))
buf[i0:i1] += seg * np.linspace(0.8, 1.0, len(seg))
# a falling sweep into the reveal
t = tt(0.6)
put(A.reveal - 0.6, filt(noise(0.6), "band", [400, 3000]) * np.linspace(0, 0.25, len(t)))

# reveal: the music opens on the brand
put(A.reveal, sub_hit(0.8)); put(A.reveal, crash(0.7), send=0.3)
put(A.reveal, keys(PROG[0][1], 1.6, 1.2), send=0.5)

# product groove
for k in bars_in(A.reveal + 0.4, A.build):
    groove(k, full=True, v=0.7)

# build into the payoff: the build — kick on every beat, snare roll, rising filter
build = np.zeros(N)
saved = buf; buf = build
for k in bars_in(A.build - 0.2, PAYOFF):
    t = bar_time(k); root, ch = chord_at(k)
    for b in range(4):
        put(t + b * B, kick(0.85))
        put(t + b * B + 2 * S, bass(root, B * 0.4, 0.9))
    for s in range(0, 16, 2):
        put(t + s * S, pluck(ch[(s // 2) % 4] + 12, 0.25, 0.8, bright=1.2), send=0.2)
    put(t, pad(ch, BAR + 0.2, 0.9), send=0.3)
buf = saved
i0, i1 = int((A.build - 0.2) * SR), int(PAYOFF * SR)
seg = build[i0:i1]
cut = np.linspace(0, 1, len(seg))
lo = filt(seg, "low", 700)
buf[i0:i1] += (lo * (1 - cut) + seg * cut) * (0.45 + 0.6 * cut ** 1.5)
# snare roll: 8ths → 16ths → 32nds across the last two bars
roll_start = PAYOFF - 1 * BAR
t = roll_start
while t < PAYOFF - 0.02:
    p = (t - roll_start) / (1 * BAR)
    put(t, snare(0.25 + 0.6 * p))
    t += S * 2 if p < 0.5 else (S if p < 0.85 else S / 2)
# a beat of silence-ish before the drop: duck the last eighth
k0 = int((PAYOFF - B / 2) * SR); k1 = int(PAYOFF * SR)
buf[k0:k1] *= np.linspace(1, 0.15, k1 - k0)

# PAYOFF: biggest moment
put(PAYOFF, sub_hit(1.0)); put(PAYOFF, crash(1.0), send=0.3)
for k in bars_in(PAYOFF, A.claim):
    groove(k, full=True, v=1.0)
    t = bar_time(k); root, ch = chord_at(k)
    for s in range(1, 16, 2):   # sparkle counter-line, 16ths, an octave up
        put(t + s * S, pluck(ch[(s // 2) % 4] + 24, 0.18, 0.45, bright=2.0), send=0.4)

# claim breakdown: breakdown — keys + pad only, a pickup into the logo
for k in bars_in(A.claim, LOGO - 0.1):
    t = bar_time(k); root, ch = chord_at(k)
    put(t, keys(ch, 1.6, 0.7), send=0.5)
    put(t + 2 * B, keys(ch[1:], 1.2, 0.5), send=0.5)
    put(t, pad(ch, BAR + 0.3, 0.8), send=0.5)
    put(t, bass(root, BAR * 0.9, 0.4))
for i, s in enumerate((-4, -3, -2, -1)):
    put(LOGO + s * S, snare(0.3 + 0.12 * i))

# logo hit, then a resolving tail to the end
put(LOGO, sub_hit(1.0)); put(LOGO, crash(0.8), send=0.3); put(LOGO, kick(1.0))
root, ch = PROG[0]
put(LOGO, keys(ch, 3.8, 1.3), send=0.6)
put(LOGO, pad(ch, 4.0, 1.3), send=0.6)
put(LOGO, bass(root, 2.6, 0.9))
for i in range(6):
    put(LOGO + 2 * B + i * 2 * S, pluck(ch[i % 4] + 12, 0.4, 0.5 - i * 0.06, bright=1.4), send=0.5)

# ---------------------------------------------------------------- mix
ir_t = tt(1.4)
ir = noise(1.4) * np.exp(-ir_t * 4.2)
ir = filt(ir, "low", 6000) * 0.012
verb = fftconvolve(verb_send, ir)[:N]
mix = buf + verb
mix = filt(mix, "high", 30)
# soft clip, master fade
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
fade_in = int(0.05 * SR)
mix[:fade_in] *= np.linspace(0, 1, fade_in)
end = int(TOTAL * SR)
fo = int(1.2 * SR)
mix[end - fo:end] *= np.linspace(1, 0, fo) ** 1.5
mix = mix[:end]
mix /= np.max(np.abs(mix)) + 1e-9
mix *= 0.89

stereo = np.stack([mix, np.roll(mix, int(0.0007 * SR))], axis=1)
pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f"wrote {sys.argv[1]}  {TOTAL}s  {BPM} BPM  payoff {PAYOFF}s  logo {LOGO:.3f}s")
