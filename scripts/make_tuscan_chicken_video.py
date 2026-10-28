#!/usr/bin/env python3
"""Build the 24-second vertical Healthy Tuscan Chicken short from three narrated clips.

The clips' audio (voice-over plus cooking sound) is laid end to end untouched,
so the voice is continuous and nothing is cut or overlapped: 3 x 8s = 24s.
To still get real 0.3s cross-dissolves, each clip's picture is stretched by a
few percent so it reaches 0.15s past its audio on each side, and the dissolves
are centred on the audio joins. No frames are frozen, and picture and sound
never drift apart by more than ~75ms.

Audio: each clip is split into voice and "everything else" with Spleeter
(sherpa-onnx). The cooking sound is taken as original minus voice and lowered
slightly (DUCK) while the voice speaks, so the result stays close to the
original recording. The whole track is then normalised to -14 LUFS.

Picture: every shot is graded toward one warm look (median brightness and
warmth of the footage, nudged warmer), framed to 1080x1920 @ 30fps, and
overlaid with the title cards and the "Spoon & Hearth" mark.

Usage:
    python3 scripts/make_tuscan_chicken_video.py sear.mp4 sauce.mp4 serve.mp4 \
        --words scripts/tuscan_chicken_words.json --font Poppins-Bold.ttf \
        --spleeter DIR -o tuscan_chicken_final.mp4

DIR is an extracted sherpa-onnx-spleeter-2stems release from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/source-separation-models
"""
import argparse
import json
import os
import statistics
import tempfile
import wave

import numpy as np

import make_chickpeas_video as base
from make_chickpeas_video import (duration, find_shots, frames, grade_for, loudnorm_apply,
                                  loudnorm_measure, run)
from make_protein_bites_video import esc

W, H, FPS = base.W, base.H, base.FPS
FADE = 0.3            # cross-dissolve, centred on each audio join
SR = 44100
DUCK = 0.7            # cooking-sound gain while the voice speaks (about -3 dB)
DUCK_RAMP = 0.12      # s, smoothing of the duck in and out
JOIN_FADE = 0.015     # s, de-click at the audio joins
CRF = 18
WARMER = 4.0          # added to the footage's median warmth for the target look

TEXTS = [  # (text, start, end, size)
    ("Healthy Tuscan Chicken", 0.0, 3.0, 70),
    ("Greek yogurt instead of cream", 8.0, 11.0, 58),
    ("44g protein • 30 min • 1 pan", 18.0, 22.0, 58),
]
TEXT_Y = 0.13         # cards sit in the top band, above the skillet
TEXT_FADE = 0.3
# Optional big hook: (lines, start, end, size, y). It is on screen from its
# first frame (no fade-in) and fades out like the other cards.
HOOK = None
MARK = "Spoon & Hearth"
MARK_SIZE = 38
MARK_FROM = None      # source time in the last clip where the mark starts; None = its last cut
# Optional {clip index: [(start, end), ...]} spans removed from the separated
# voice only (e.g. a line recorded twice). Later speech slides earlier; the
# cooking sound stays where it is, in sync with the picture.
VOICE_CUTS = {}
SPLICE = 0.01         # s, crossfade at each voice splice
CLIP_SECONDS = None   # trim each clip's silent tail to this length (e.g. 8.0 for a 24s total)


def separate(src, model, tmp, tag):
    """(original, voice) as float32 arrays (2, n) at SR, edges padded for the model."""
    import sherpa_onnx as so
    raw = run(["ffmpeg", "-v", "error", "-i", src, "-ar", str(SR), "-ac", "2", "-f", "f32le", "-"],
              capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()
    cfg = so.OfflineSourceSeparationConfig(model=so.OfflineSourceSeparationModelConfig(
        spleeter=so.OfflineSourceSeparationSpleeterModelConfig(
            vocals=f"{model}/vocals.onnx", accompaniment=f"{model}/accompaniment.onnx"),
        num_threads=4))
    pad = SR  # the model produces garbage in its first/last chunk; pad and crop
    xp = np.pad(x, ((0, 0), (pad, pad + 4096))).astype(np.float32)
    voice = np.array(so.OfflineSourceSeparation(cfg).process(SR, xp).stems[0].data)
    return x, voice[:, pad:pad + x.shape[1]]


def duck_curve(n, words):
    """Per-sample gain for the cooking sound: DUCK while words are spoken, 1 elsewhere."""
    g = np.ones(n)
    for _, a, b in words:
        g[int(max(0, a - 0.05) * SR):int((b + 0.05) * SR)] = DUCK
    k = int(DUCK_RAMP * SR)
    kernel = np.ones(k) / k
    return np.convolve(np.pad(g, (k, k), mode="edge"), kernel, mode="same")[k:-k]


def cut_voice(voice, words, a, b):
    """Remove [a, b) seconds from the voice, pad its end with silence, shift the words."""
    i, j, k = int(a * SR), int(b * SR), int(SPLICE * SR)
    head, tail = voice[:, :i].copy(), voice[:, j:].copy()
    ramp = np.linspace(0, 1, k)
    head[:, -k:] = head[:, -k:] * ramp[::-1] + tail[:, :k] * ramp
    out = np.concatenate([head, tail[:, k:], np.zeros((2, j - i + k))], axis=1)
    shifted = [(w, s - (b - a), e - (b - a)) if s >= b else (w, s, e)
               for w, s, e in words if s >= b or e <= a]
    return out[:, :voice.shape[1]], shifted


def write_wav(path, x):
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render_stretched(src, length, dst, log):
    """Graded 1080x1920@30 picture of the whole clip, stretched to `length` seconds."""
    dur = duration(src)
    rgb = frames(src)
    rate = len(rgb) / dur
    parts, labels = [], []
    for k, (a, b) in enumerate(find_shots(src, dur)):
        grade, summary = grade_for(rgb[int(a * rate):max(int(a * rate) + 1, int(b * rate))])
        log.append(f"    shot {a:4.2f}-{b:4.2f}s: {summary}")
        parts.append(f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS,{grade}[p{k}]")
        labels.append(f"[p{k}]")
    fc = ";".join(parts) + ";" + "".join(labels) + (
        f"concat=n={len(labels)}:v=1:a=0,setpts={length / dur:.6f}*(PTS-STARTPTS),"
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
        f"fps={FPS},format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]",
         "-t", f"{length:.4f}", "-c:v", "libx264", "-crf", "14", "-preset", "medium", dst])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=3)
    ap.add_argument("--words", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--spleeter", required=True)
    ap.add_argument("-o", "--output", default="tuscan_chicken_final.mp4")
    args = ap.parse_args()

    words = [c["words"] for c in json.load(open(args.words))]
    n = len(args.clips)
    tmp = tempfile.mkdtemp(prefix="tuscan_")
    if CLIP_SECONDS:
        clips = []
        for i, src in enumerate(args.clips):
            if duration(src) > CLIP_SECONDS + 1e-3:
                assert words[i][-1][2] < CLIP_SECONDS, f"trim would cut speech in clip {i + 1}"
                cut = os.path.join(tmp, f"trim{i}.mkv")
                run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", f"{CLIP_SECONDS:.3f}",
                     "-c:v", "libx264", "-crf", "10", "-preset", "fast", "-c:a", "pcm_s16le", cut])
                src = cut
            clips.append(src)
        args.clips = clips
    durs = [duration(c) for c in args.clips]
    log = []

    # ---- timeline: audio back to back; picture overlaps by FADE/2 each side of a join
    a_start = [sum(durs[:i]) for i in range(n)]
    total = sum(durs)
    h = FADE / 2
    v_start = [a_start[i] - (h if i else 0) for i in range(n)]
    v_len = [durs[i] + (h if i else 0) + (h if i < n - 1 else 0) for i in range(n)]
    for i in range(n):
        k = v_len[i] / durs[i]
        drift = max(abs(v_start[i] - a_start[i]),
                    abs(v_start[i] + v_len[i] - a_start[i] - durs[i]))
        log.append(f"  clip {i + 1}: audio {a_start[i]:.2f}-{a_start[i] + durs[i]:.2f}s, picture "
                   f"{v_start[i]:.2f}-{v_start[i] + v_len[i]:.2f}s (stretched x{k:.4f}, "
                   f"max picture/sound offset {drift * 1000:.0f}ms at the clip edges, 0 mid-clip)")

    # ---- grade target from the footage itself
    lumas, warmths = [], []
    for src in args.clips:
        rgb = frames(src)
        rate = len(rgb) / duration(src)
        for a, b in find_shots(src, duration(src)):
            m = rgb[int(a * rate):max(int(a * rate) + 1, int(b * rate))].reshape(-1, 3).mean(0)
            lumas.append(0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2])
            warmths.append(m[0] - m[2])
    base.TARGET_LUMA = statistics.median(lumas)
    base.TARGET_WARMTH = statistics.median(warmths) + WARMER
    base.TARGET_CONTRAST = 62.0
    base.GRADE_STRENGTH = 0.7
    log.append(f"  grade target: luma {base.TARGET_LUMA:.0f}, warmth {base.TARGET_WARMTH:.0f}")

    vids = []
    for i, src in enumerate(args.clips):
        log.append(f"  clip {i + 1} shots:")
        dst = os.path.join(tmp, f"v{i}.mp4")
        render_stretched(src, v_len[i], dst, log)
        vids.append(dst)

    # ---- audio: duck the cooking sound under the voice, join back to back
    pieces = []
    for i, src in enumerate(args.clips):
        x, voice = separate(src, args.spleeter, tmp, i)
        cooking = x - voice
        clip_words = words[i]
        for a, b in sorted(VOICE_CUTS.get(i, []), reverse=True):
            voice, clip_words = cut_voice(voice, clip_words, a, b)
            log.append(f"  clip {i + 1} audio: removed {a:.2f}-{b:.2f}s from the voice, "
                       f"later speech moved {b - a:.2f}s earlier")
        g = duck_curve(x.shape[1], clip_words)
        y = voice + g * cooking
        j = int(JOIN_FADE * SR)
        ramp = np.linspace(0, 1, j)
        if i:
            y[:, :j] *= ramp
        if i < n - 1:
            y[:, -j:] *= ramp[::-1]
        log.append(f"  clip {i + 1} audio: voice separated, cooking sound x{DUCK} under speech")
        pieces.append(y)
    joined = os.path.join(tmp, "joined.wav")
    write_wav(joined, np.concatenate(pieces, axis=1))
    final_audio = os.path.join(tmp, "final.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-af",
         loudnorm_apply(loudnorm_measure(joined)) + ",aresample=48000", "-ar", "48000", final_audio])

    # ---- picture: dissolves + text
    ins, fc = [], []
    for v in vids:
        ins += ["-i", v]
    ins += ["-i", final_audio]
    v = "[0:v]"
    for i in range(1, n):
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={FADE}:offset={v_start[i]:.4f}[x{i}]")
        v = f"[x{i}]"
    count = [0]

    def draw(txt, size, x, y, t0, t1, fade, fade_in=None):
        nonlocal v
        count[0] += 1
        fade_in = fade if fade_in is None else fade_in
        alpha = f"if(gt(t,{t1 - fade:.3f}),max(0,({t1:.3f}-t)/{fade}),1)"
        if fade_in:
            alpha = f"if(lt(t,{t0 + fade_in:.3f}),(t-{t0:.3f})/{fade_in},{alpha})"
        fc.append(f"{v}drawtext=fontfile={args.font}:text='{esc(txt)}':fontsize={size}:"
                  f"fontcolor=white:shadowcolor=black@0.7:shadowx=3:shadowy=5:"
                  f"borderw=3:bordercolor=black@0.5:x={x}:y={y}:alpha='{alpha}':"
                  f"enable='between(t,{t0:.3f},{t1:.3f})'[t{count[0]}]")
        v = f"[t{count[0]}]"

    if HOOK:
        lines, t0, t1, size, y = HOOK
        for j, line in enumerate(lines):
            draw(line, size, "(w-text_w)/2", f"h*{y}+{int(j * size * 1.15)}", t0, t1, TEXT_FADE,
                 fade_in=0)
    for txt, t0, t1, size in TEXTS:  # "\n" splits a card over two lines
        for j, line in enumerate(txt.split("\n")):
            draw(line, size, "(w-text_w)/2", f"h*{TEXT_Y}+{int(j * size * 1.2)}", t0, t1, TEXT_FADE)
    # Brand mark over the final bite shot: the last shot of the last clip.
    last_shot = MARK_FROM if MARK_FROM is not None else find_shots(args.clips[-1], durs[-1])[-1][0]
    mark_t0 = v_start[-1] + last_shot * v_len[-1] / durs[-1]
    draw(MARK, MARK_SIZE, f"w-text_w-56", f"h-text_h-{int(H * 0.06)}", mark_t0, total + 1, 0.4)
    log.append(f"  '{MARK}' from {mark_t0:.2f}s (final bite shot) to the end")

    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc),
         "-map", v, "-map", f"{n}:a", "-t", f"{total:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-crf", str(CRF), "-preset", "slow", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", args.output])
    print("\n".join(log))
    print(f"wrote {args.output} ({total:.2f}s)")


if __name__ == "__main__":
    main()
