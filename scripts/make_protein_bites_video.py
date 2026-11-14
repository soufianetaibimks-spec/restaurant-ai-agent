#!/usr/bin/env python3
"""Build the vertical peanut-butter protein-bites short from three self-narrated clips.

Same workflow as make_chickpeas_video.py (whose helpers it reuses): the clips
keep their own voice-over and kitchen sound, every shot is graded toward one
look, clips are joined with 0.3s crossfades, and captions follow the word
timings from transcribe_clips.py. Differences from the chickpeas edit:

  * silent tails are trimmed to a short pause, never into a word, and never
    padded with held frames;
  * captions are 2-4 word lines in Poppins Bold with key words in #FFC845,
    shown exactly while their words are spoken;
  * hook title (0-2s), top-left STEP labels at each clip start, end card in
    the last 2s;
  * no denoising, so the kitchen ASMR stays under the voice.

Usage:
    python3 scripts/make_protein_bites_video.py clip1.mp4 clip2.mp4 clip3.mp4 \
        --words scripts/protein_bites_words.json --font Poppins-Bold.ttf \
        -o peanut_butter_bites_final.mp4
"""
import argparse
import json
import os
import tempfile

from PIL import ImageFont

import make_chickpeas_video as base
from make_chickpeas_video import duration, loudnorm_apply, loudnorm_measure, render_clip, run

W, H, FPS = base.W, base.H, base.FPS
FADE = 0.3
PAUSE = 0.45        # silence kept after a clip's last word before its outgoing fade
TAIL_MIN = 0.25     # never end the video sooner than this after the final word
CRF = 18
YELLOW = "0xFFC845"

# Warm, golden, slightly bright.
base.TARGET_LUMA, base.TARGET_WARMTH, base.TARGET_CONTRAST = 150.0, 76.0, 62.0
base.GRADE_STRENGTH = 0.7

HOOK = ["3-Ingredient", "Protein Bites"]
HOOK_SECONDS = 2.0
STEPS = ["STEP 1", "STEP 2", "STEP 3"]
STEP_SECONDS = 2.5
END_CARD = ["12g protein each • No bake", "Full recipe: Spoon & Hearth"]
END_SECONDS = 2.0

# One caption line per entry: (text with *highlighted words*, aligned words covered).
CAPTIONS = [
    [("Just *three ingredients*", 3), ("and *no baking.*", 3), ("Start by *mashing*", 3),
     ("one *ripe banana*", 3), ("until it's *smooth.*", 4)],
    [("Stir in a *cup*", 4), ("of *peanut butter,*", 3), ("then a *cup*", 3),
     ("of *protein powder*", 3), ("until a *thick*", 3), ("*dough* forms.", 2)],
    [("Roll into *12 bites*", 4), ("and *chill*", 2), ("for *20 minutes.*", 3),
     ("*12 grams*", 2), ("of *protein* each.", 3), ("*Full recipe* on", 3),
     ("*Spoon & Hearth.*", 3)],
]
CAP_SIZE, CAP_Y = 66, 0.675      # line centre at 67.5% of the height
CAP_MAX_W = 780                  # px; keeps clear of the right-hand button column
CAP_LINGER = 0.12                # caption stays this long after its last word ends


def esc(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def parse_caption(text):
    """'of *peanut butter,*' -> [('of', False), ('peanut', True), ('butter,', True)]"""
    out, hl = [], False
    for word in text.split():
        start = word.startswith("*")
        end = word.endswith("*")
        hl = hl or start
        out.append((word.strip("*"), hl))
        if end:
            hl = False
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=3)
    ap.add_argument("--words", required=True)
    ap.add_argument("--font", required=True, help="bold rounded sans TTF, e.g. Poppins-Bold")
    ap.add_argument("-o", "--output", default="peanut_butter_bites_final.mp4")
    args = ap.parse_args()

    words = [c["words"] for c in json.load(open(args.words))]
    for cap, w in zip(CAPTIONS, words):
        assert sum(n for _, n in cap) == len(w), "caption word counts must match the transcript"
    n = len(args.clips)
    durs = [duration(c) for c in args.clips]
    font = args.font
    measure = ImageFont.truetype(font, CAP_SIZE)

    # Trim only silent tails: keep PAUSE after the last word plus the crossfade,
    # and make sure the next clip's first word cannot land inside that fade.
    lengths = []
    for i in range(n):
        last = words[i][-1][2]
        if i < n - 1:
            keep = last + PAUSE + FADE - min(words[i + 1][0][1], PAUSE)
        else:
            keep = last + TAIL_MIN
        lengths.append(min(durs[i], max(keep, last + 0.05)))
    starts = [0.0]
    for L in lengths[:-1]:
        starts.append(starts[-1] + L - FADE)
    total = starts[-1] + lengths[-1]

    tmp = tempfile.mkdtemp(prefix="pbbites_")
    log = []
    vids = []
    for i, src in enumerate(args.clips):
        log.append(f"  clip {i + 1}: {durs[i]:.2f}s source -> {lengths[i]:.2f}s "
                   f"(trimmed {durs[i] - lengths[i]:.2f}s silent tail), at {starts[i]:.2f}s")
        dst = os.path.join(tmp, f"v{i}.mp4")
        hold = render_clip(src, lengths[i], dst, log)
        assert hold == 0, "a clip would need a held frame"
        vids.append(dst)

    # ---- audio: per-clip loudness match (voice + kitchen sound together), joins
    # crossfaded over FADE, then the whole track to -14 LUFS.
    auds = []
    for i, src in enumerate(args.clips):
        pre = "highpass=f=60"
        m = loudnorm_measure(src, pre)
        # Incoming clips fade in over the crossfade, but never across their first word.
        fade_in = min(FADE, max(0.03, words[i][0][1] - 0.02)) if i else 0.0
        out_d = FADE if i < n - 1 else 0.2
        af = (f"{pre},{loudnorm_apply(m)},aresample=48000,atrim=0:{lengths[i]:.3f},"
              f"apad=whole_dur={lengths[i]:.3f},"
              + (f"afade=t=in:d={fade_in:.3f}," if fade_in else "")
              + f"afade=t=out:st={lengths[i] - out_d:.3f}:d={out_d}")
        dst = os.path.join(tmp, f"a{i}.wav")
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-af", af, "-ac", "2", "-ar", "48000", dst])
        log.append(f"  clip {i + 1} audio: {m['input_i']} LUFS -> -14, fade in {fade_in:.2f}s")
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
    for v in vids:
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
        label = f"d{count[0]}"
        alpha = ""
        if fade:
            alpha = (f":alpha='if(lt(t,{t0 + fade:.3f}),(t-{t0:.3f})/{fade},"
                     f"if(gt(t,{t1 - fade:.3f}),max(0,({t1:.3f}-t)/{fade}),1))'")
        fc.append(f"{v}drawtext=fontfile={font}:text='{esc(txt)}':fontsize={size}:fontcolor={color}:"
                  f"borderw={max(3, size // 16)}:bordercolor=black@0.65:shadowcolor=black@0.45:"
                  f"shadowx=2:shadowy=4:x={x}:y={y}{alpha}{extra}:"
                  f"enable='between(t,{t0:.3f},{t1:.3f})'[{label}]")
        v = f"[{label}]"

    # Word-by-word captions share a baseline (y is set from the font ascent), so
    # short words like "a" do not float above the rest of the line.
    # Hook title, top safe area.
    for j, line in enumerate(HOOK):
        draw(line, 92, "(w-text_w)/2", f"h*0.15+{j * 112}", 0, HOOK_SECONDS, fade=0.3)
    # STEP labels, top-left, as each clip starts.
    for i, step in enumerate(STEPS[:n]):
        t0 = starts[i] + (FADE if i else 0)
        draw(step, 50, "70", "h*0.08", t0, t0 + STEP_SECONDS, fade=0.25,
             extra=":box=1:boxcolor=black@0.35:boxborderw=16")
    # End card, upper-middle so it never meets the captions.
    for j, line in enumerate(END_CARD):
        draw(line, 62 if j == 0 else 56, "(w-text_w)/2", f"h*0.17+{j * 92}",
             total - END_SECONDS, total, color=YELLOW if j == 0 else "white", fade=0.35)

    # Captions: one line each, words laid out individually so key words can be yellow.
    caps = []
    for i, cap in enumerate(CAPTIONS):
        k = 0
        for txt, cnt in cap:
            seg = words[i][k:k + cnt]
            caps.append((txt, starts[i] + seg[0][1], starts[i] + seg[-1][2]))
            k += cnt
    space = measure.getlength(" ")
    report = []
    for c, (txt, a, b) in enumerate(caps):
        end = b + CAP_LINGER
        if c + 1 < len(caps):
            end = min(end, caps[c + 1][1] - 1 / FPS)
        parts = parse_caption(txt)
        widths = [measure.getlength(w) for w, _ in parts]
        line_w = sum(widths) + space * (len(parts) - 1)
        assert line_w <= CAP_MAX_W, f"caption too wide ({line_w:.0f}px): {txt}"
        x = (W - line_w) / 2
        for (word, hl), wpx in zip(parts, widths):
            draw(word, CAP_SIZE, f"{x:.1f}", f"h*{CAP_Y}+{CAP_SIZE // 3}-ascent", a, end,
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
