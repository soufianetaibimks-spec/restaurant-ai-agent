#!/usr/bin/env python3
"""Build the vertical veggie egg-muffins short from three self-narrated clips.

Same workflow as make_protein_bites_video.py: clips keep their own voice-over
and kitchen sound, every shot is graded toward one look, 0.3s crossfades join
the clips, and 2-4 word Poppins captions (key words in #FFC845) follow the
word timings from transcribe_clips.py. Differences:

  * only dead frames are trimmed: static footage (no motion) at a clip's head
    or tail, never into a word. Silent-but-moving footage is kept;
  * captions sit in the upper third (25% down), clear of the food and the
    right-hand buttons;
  * the grade's warmth target is the median of the footage's own shots, so
    the look stays natural while brightness is lifted slightly;
  * STEP labels at the very top-left, the hook title just below them, and the
    end card in the empty strip above the captions.

Usage:
    python3 scripts/make_egg_muffins_video.py clip1.mp4 clip2.mp4 clip3.mp4 \
        --words scripts/egg_muffins_words.json --font Poppins-Bold.ttf \
        -o veggie_egg_muffins_final.mp4
"""
import argparse
import json
import os
import statistics
import tempfile

import numpy as np
from PIL import ImageFont

import make_chickpeas_video as base
from make_chickpeas_video import (duration, find_shots, frames, loudnorm_apply,
                                  loudnorm_measure, render_clip, run)
from make_protein_bites_video import esc, parse_caption

W, H, FPS = base.W, base.H, base.FPS
FADE = 0.3
CRF = 18
YELLOW = "0xFFC845"
DEAD_MOTION = 0.8     # mean abs frame difference (0-255) below which footage is dead
WORD_MARGIN = 0.15    # never trim closer than this to a word

base.TARGET_LUMA, base.TARGET_CONTRAST = 150.0, 62.0  # warmth set from the footage
base.GRADE_STRENGTH = 0.7

HOOK = "High-Protein Egg Muffins"
HOOK_SECONDS = 2.0
STEPS = ["STEP 1", "STEP 2", "STEP 3"]
STEP_SECONDS = 2.5
END_CARD = ["19g protein • Meal prep breakfast", "Full recipe: Spoon & Hearth"]
END_SECONDS = 2.0

# One caption line per entry: (text with *highlighted words*, aligned words covered).
CAPTIONS = [
    [("*Breakfast* for", 2), ("the *whole week*", 3), ("in *30 minutes.*", 3),
     ("Start by *filling*", 3), ("a *muffin tin*", 3), ("with *spinach,*", 2),
     ("*peppers,* *onion,*", 2), ("and *feta.*", 2)],
    [("Whisk *10 eggs*", 3), ("with a *splash*", 3), ("of *milk,*", 2), ("*pour* it over", 3),
     ("the *veggies,*", 2), ("and *bake*", 2), ("for about *20 minutes.*", 4)],
    [("*Puffed,* *golden,*", 2), ("and *19 grams*", 3), ("of *protein*", 2),
     ("per *serving.*", 2), ("*Meal prep* done.", 3), ("*Full recipe* on", 3),
     ("*Spoon & Hearth.*", 3)],
]
CAP_SIZE, CAP_Y = 68, 0.25    # caption baseline sits at 25% of the height
CAP_MAX_W = 780
CAP_LINGER = 0.12

STEP_Y, HOOK_Y, END_Y = 0.045, 0.115, 0.09   # all above the caption band


def motion(path):
    g = frames(path, 45, 80, "gray", 1)[..., 0]
    return np.abs(np.diff(g, axis=0)).mean(1), len(g) / duration(path)


def live_window(path, first_word, last_word):
    """(start, end) after dropping static frames at the head and tail."""
    d, rate = motion(path)
    dur = duration(path)
    start, end = 0.0, dur
    i = 0
    while i < len(d) and d[i] < DEAD_MOTION and (i + 1) / rate < first_word - WORD_MARGIN:
        i += 1
    start = i / rate
    j = len(d) - 1
    while j > 0 and d[j] < DEAD_MOTION and j / rate > last_word + WORD_MARGIN:
        j -= 1
    end = min(dur, (j + 2) / rate)
    return start, end


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=3)
    ap.add_argument("--words", required=True)
    ap.add_argument("--font", required=True, help="bold rounded sans TTF, e.g. Poppins-Bold")
    ap.add_argument("-o", "--output", default="veggie_egg_muffins_final.mp4")
    args = ap.parse_args()

    words = [c["words"] for c in json.load(open(args.words))]
    for cap, w in zip(CAPTIONS, words):
        assert sum(n for _, n in cap) == len(w), "caption word counts must match the transcript"
    n = len(args.clips)
    font = args.font
    measure = ImageFont.truetype(font, CAP_SIZE)
    space = measure.getlength(" ")
    for cap in CAPTIONS:  # fail before rendering if a line would not fit
        for txt, _ in cap:
            parts = parse_caption(txt)
            wide = sum(measure.getlength(w) for w, _ in parts) + space * (len(parts) - 1)
            assert wide <= CAP_MAX_W, f"caption too wide ({wide:.0f}px): {txt}"

    # Natural warmth: the median warmth of all shots in the footage.
    warmths = []
    for src in args.clips:
        rgb = frames(src)
        rate = len(rgb) / duration(src)
        for a, b in find_shots(src, duration(src)):
            m = rgb[int(a * rate):max(int(a * rate) + 1, int(b * rate))].reshape(-1, 3).mean(0)
            warmths.append(m[0] - m[2])
    base.TARGET_WARMTH = statistics.median(warmths)

    # Dead-frame trims, then the timeline.
    windows = [live_window(c, w[0][1], w[-1][2]) for c, w in zip(args.clips, words)]
    words = [[(t, s - win[0], e - win[0]) for t, s, e in w] for w, win in zip(words, windows)]
    lengths = [b - a for a, b in windows]
    starts = [0.0]
    for L in lengths[:-1]:
        starts.append(starts[-1] + L - FADE)
    total = starts[-1] + lengths[-1]

    tmp = tempfile.mkdtemp(prefix="eggmuffins_")
    log = [f"  grade target: luma {base.TARGET_LUMA:.0f}, warmth {base.TARGET_WARMTH:.0f} "
           f"(median of {len(warmths)} shots)"]
    vids = []
    for i, src in enumerate(args.clips):
        a, b = windows[i]
        log.append(f"  clip {i + 1}: {duration(src):.2f}s source, using {a:.2f}-{b:.2f}s "
                   f"({lengths[i]:.2f}s) at {starts[i]:.2f}s")
        cut = src
        if a > 0:
            cut = os.path.join(tmp, f"cut{i}.mp4")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b - a:.3f}",
                 "-c:v", "libx264", "-crf", "12", "-c:a", "pcm_s16le", cut.replace(".mp4", ".mkv")])
            cut = cut.replace(".mp4", ".mkv")
        dst = os.path.join(tmp, f"v{i}.mp4")
        hold = render_clip(cut, lengths[i], dst, log)
        assert hold < 1 / FPS, "a clip would need a held frame"
        vids.append((dst, cut))

    # ---- audio: per-clip loudness match (voice + kitchen sound), crossfaded joins,
    # whole track to -14 LUFS.
    auds = []
    for i, (_, src) in enumerate(vids):
        pre = "highpass=f=60"
        m = loudnorm_measure(src, pre)
        fade_in = min(FADE, max(0.03, words[i][0][1] - 0.02)) if i else 0.0
        out_d = FADE if i < n - 1 else 0.25
        af = (f"{pre},{loudnorm_apply(m)},aresample=48000,atrim=0:{lengths[i]:.3f},"
              f"apad=whole_dur={lengths[i]:.3f},"
              + (f"afade=t=in:d={fade_in:.3f}," if fade_in else "")
              + f"afade=t=out:st={lengths[i] - out_d:.3f}:d={out_d}")
        dst = os.path.join(tmp, f"a{i}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-af", af, "-ac", "2", "-ar", "48000", dst])
        log.append(f"  clip {i + 1} audio: {m['input_i']} LUFS -> -14, fade in {fade_in:.2f}s, "
                   f"fade out {out_d:.2f}s")
        auds.append(dst)
    mix = os.path.join(tmp, "mix.wav")
    ins, fc = [], []
    for i, a in enumerate(auds):
        ins += ["-i", a]
        ms = int(round(starts[i] * 1000))
        fc.append(f"[{i}:a]adelay={ms}|{ms}[d{i}]")
    fc.append("".join(f"[d{i}]" for i in range(n)) +
              f"amix=inputs={n}:duration=longest:normalize=0,atrim=0:{total:.3f}[m]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[m]", mix])
    final_audio = os.path.join(tmp, "final.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", mix, "-af", loudnorm_apply(loudnorm_measure(mix)),
         "-ar", "48000", final_audio])

    # ---- picture
    ins, fc = [], []
    for v, _ in vids:
        ins += ["-i", v]
    ins += ["-i", final_audio]
    v = "[0:v]"
    for i in range(1, n):
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={FADE}:offset={starts[i]:.3f}[x{i}]")
        v = f"[x{i}]"
    count = [0]

    def draw(txt, size, x, y, t0, t1, color="white", fade=0.0, extra=""):
        nonlocal v
        count[0] += 1
        alpha = ""
        if fade:
            alpha = (f":alpha='if(lt(t,{t0 + fade:.3f}),(t-{t0:.3f})/{fade},"
                     f"if(gt(t,{t1 - fade:.3f}),max(0,({t1:.3f}-t)/{fade}),1))'")
        fc.append(f"{v}drawtext=fontfile={font}:text='{esc(txt)}':fontsize={size}:fontcolor={color}:"
                  f"borderw={max(3, size // 16)}:bordercolor=black@0.65:shadowcolor=black@0.45:"
                  f"shadowx=2:shadowy=4:x={x}:y={y}{alpha}{extra}:"
                  f"enable='between(t,{t0:.3f},{t1:.3f})'[o{count[0]}]")
        v = f"[o{count[0]}]"

    draw(HOOK, 76, "(w-text_w)/2", f"h*{HOOK_Y}", 0, HOOK_SECONDS, fade=0.3)
    for i, step in enumerate(STEPS[:n]):
        t0 = starts[i] + (FADE if i else 0)
        draw(step, 46, "64", f"h*{STEP_Y}", t0, t0 + STEP_SECONDS, fade=0.25,
             extra=":box=1:boxcolor=black@0.35:boxborderw=14")
    for j, line in enumerate(END_CARD):
        draw(line, 58 if j == 0 else 52, "(w-text_w)/2", f"h*{END_Y}+{j * 80}",
             total - END_SECONDS, total, color=YELLOW if j == 0 else "white", fade=0.35)

    # Captions: one line each, words drawn on a shared baseline so key words can be yellow.
    caps = []
    for i, cap in enumerate(CAPTIONS):
        k = 0
        for txt, cnt in cap:
            seg = words[i][k:k + cnt]
            caps.append((txt, starts[i] + seg[0][1], starts[i] + seg[-1][2]))
            k += cnt
    report = []
    for c, (txt, a, b) in enumerate(caps):
        end = b + CAP_LINGER
        if c + 1 < len(caps):
            end = min(end, caps[c + 1][1] - 1 / FPS)
        parts = parse_caption(txt)
        widths = [measure.getlength(w) for w, _ in parts]
        x = (W - (sum(widths) + space * (len(parts) - 1))) / 2
        for (word, hl), wpx in zip(parts, widths):
            draw(word, CAP_SIZE, f"{x:.1f}", f"h*{CAP_Y}-ascent", a, end,
                 color=YELLOW if hl else "white")
            x += wpx + space
        report.append(f"  {a:6.2f}-{end:6.2f}  {txt.replace('*', '')}")

    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc),
         "-map", v, "-map", f"{n}:a", "-t", f"{total:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-crf", str(CRF), "-preset", "slow", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", args.output])

    print("\n".join(log))
    print("captions:")
    print("\n".join(report))
    print(f"wrote {args.output} ({total:.2f}s)")


if __name__ == "__main__":
    main()
