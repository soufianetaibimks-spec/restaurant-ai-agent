#!/usr/bin/env python3
"""Synthesise a soft, warm fingerpicked acoustic-guitar bed (royalty-free: generated here).

Karplus-Strong plucked strings play a Cmaj7 - Am7 - Fmaj7 - G arpeggio at a
relaxed tempo, with a gentle low-pass for warmth, slight timing/velocity
humanisation, stereo spread and a small reverb tail. Output is a 44.1kHz
stereo WAV peaking at -1 dBFS, with a fade in and out. Deterministic (fixed seed).

Usage:
    python3 scripts/make_acoustic_bed.py --seconds 24 -o bed.wav
"""
import argparse
import wave

import numpy as np
from scipy.signal import fftconvolve, lfilter

SR = 44100
BPM = 84
# (bass note, four upper notes) as MIDI numbers
CHORDS = [
    (48, [55, 60, 64, 71]),   # Cmaj7
    (45, [57, 60, 64, 67]),   # Am7
    (41, [57, 60, 64, 65]),   # Fmaj7
    (43, [55, 59, 62, 67]),   # G
]
# eighth-note picking pattern per bar: "B" = bass, numbers index the upper notes
PATTERN = ["B", 1, 2, 3, "b", 2, 3, 1]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def pluck(freq, seconds, rng, brightness=0.35, decay=0.996):
    """One plucked string (Karplus-Strong) as a mono float array."""
    n = int(SR / freq)
    excite = rng.uniform(-1, 1, n)
    excite = lfilter([brightness], [1, brightness - 1], excite)  # soften the attack
    x = np.zeros(int(seconds * SR))
    x[:n] = excite
    a = np.zeros(n + 2)
    a[0], a[n], a[n + 1] = 1.0, -0.5 * decay, -0.5 * decay
    y = lfilter([1.0], a, x)
    return y / (np.abs(y).max() + 1e-9)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=24.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("-o", "--output", default="acoustic_bed.wav")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    eighth = 60 / BPM / 2
    total = int((args.seconds + 3) * SR)
    out = np.zeros((2, total))
    t, bar = 0.0, 0
    while t < args.seconds + 1:
        bass, upper = CHORDS[bar % len(CHORDS)]
        for step, what in enumerate(PATTERN):
            when = t + step * eighth + rng.normal(0, 0.006)
            if what in ("B", "b"):
                note, vel, pan = bass, (0.9 if what == "B" else 0.55), 0.0
            else:
                note, vel, pan = upper[what], 0.5 + rng.uniform(-0.08, 0.08), (what - 1.5) * 0.25
            s = pluck(midi_hz(note), 3.0, rng) * vel
            i = int(max(0, when) * SR)
            j = min(total, i + len(s))
            out[0, i:j] += s[:j - i] * np.sqrt(0.5 - pan / 2)
            out[1, i:j] += s[:j - i] * np.sqrt(0.5 + pan / 2)
        t += 8 * eighth
        bar += 1

    out = lfilter([0.18], [1, -0.82], out, axis=1)  # warm one-pole low-pass (~1.4kHz knee)
    ir_len = int(1.6 * SR)
    decay = np.exp(-np.linspace(0, 6, ir_len))
    ir = np.stack([rng.normal(0, 1, ir_len) * decay for _ in range(2)]) * 0.012
    wet = np.stack([fftconvolve(out[c], ir[c])[:total] for c in range(2)])
    mix = out + wet * 0.6

    n = int(args.seconds * SR)
    mix = mix[:, :n]
    fade_in, fade_out = int(1.0 * SR), int(2.0 * SR)
    mix[:, :fade_in] *= np.linspace(0, 1, fade_in)
    mix[:, -fade_out:] *= np.linspace(1, 0, fade_out)
    mix *= 10 ** (-1 / 20) / np.abs(mix).max()

    pcm = (mix.T * 32767).astype("<i2")
    with wave.open(args.output, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {args.output} ({args.seconds:.1f}s, {BPM} bpm)")


if __name__ == "__main__":
    main()
