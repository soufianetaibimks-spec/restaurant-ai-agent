#!/usr/bin/env python3
"""Build the vertical crispy-chickpeas short from three self-narrated clips.

The clips keep their own voice-over. Each clip is used whole: only silence at
the head or tail could be trimmed, and these clips are narrated from the first
frame to the last word. Where a clip's tail is too short for the crossfade
plus a natural pause before the next clip's first word, its last frame is held
instead of cutting into speech.

Pipeline
  * video: every shot (cut inside a clip) is graded toward one shared warm
    look -> 1080x1920 @ 30fps -> 0.3s crossfades -> title card, STEP labels
    and captions synced to the spoken words.
  * audio: per clip high-pass + FFT denoise + loudness matched; clips laid on
    the timeline in sync with their video, with a short crossfade at each
    join; whole track normalised to -14 LUFS (two-pass loudnorm).

Word timings come from scripts/transcribe_clips.py.

Usage:
    python3 scripts/make_chickpeas_video.py clip1.mp4 clip2.mp4 clip3.mp4 \
        --words scripts/chickpeas_words.json -o chickpeas_final.mp4
"""
import argparse
import json
import os
import subprocess
import tempfile

import numpy as np

W, H, FPS = 1080, 1920, 30
FADE = 0.3          # video crossfade (s)
GAP = 0.25          # minimum pause between one clip's last word and the next clip's first
TAIL_MIN = 0.4      # keep at least this much after the final word of the video
LUFS = -14.0
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Shared look every shot is pulled toward (measured from the kitchen shots).
TARGET_LUMA, TARGET_WARMTH, TARGET_CONTRAST = 135.0, 50.0, 62.0
GRADE_STRENGTH = 0.8
CUT_THRESHOLD = 30.0  # mean abs frame difference (0-255) that counts as a cut

STEPS = ["STEP 1", "STEP 2", "STEP 3"]
TITLE = ["CRISPY", "CHICKPEAS"]
TITLE_SECONDS = 2.0

# Caption text per clip, each with the number of aligned words it covers.
CAPTIONS = [
    [("Craving something crunchy?", 3), ("These crispy roasted chickpeas", 5),
     ("start with just one can.", 5), ("The secret?", 2), ("Dry them really well.", 4)],
    [("Toss them with olive oil and salt,", 7), ("spread them out,", 3),
     ("and roast at 400 degrees", 6), ("until they're golden", 4),
     ("and rattle in the pan.", 5)],
    [("Season while they're hot.", 5), ("11 grams of protein.", 4), ("No added sugar.", 3),
     ("Full recipe on Spoon and Hearth.", 6)],
]
CAPTION_SIZE, CAPTION_STEP, CAPTION_Y = 68, 88, 0.65  # block centre at 65% height
CAPTION_MAX_CHARS = 19                                  # keeps lines ~760px wide


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", path], capture_output=True, text=True).stdout)


def frames(path, w=90, h=160, fmt="rgb24", ch=3):
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
               "-pix_fmt", fmt, "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h * w, ch).astype(np.float64)


def find_shots(path, dur):
    """[(start, end)] of the shots inside a clip, split at hard cuts."""
    g = frames(path, 45, 80, "gray", 1)[..., 0]
    rate = len(g) / dur
    diffs = np.abs(np.diff(g, axis=0)).mean(1)
    cuts = [(i + 1) / rate for i, d in enumerate(diffs) if d > CUT_THRESHOLD]
    edges = [0.0] + cuts + [dur]
    return list(zip(edges[:-1], edges[1:]))


def grade_for(rgb):
    """lutrgb pulling one shot's brightness, warmth and contrast toward the target."""
    m = rgb.reshape(-1, 3).mean(0)
    luma = 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]
    contrast = rgb.reshape(-1, 3).std(0).mean()
    gain = (TARGET_LUMA / luma) ** GRADE_STRENGTH                 # exposure, keeps black at 0
    con = (TARGET_CONTRAST / contrast) ** (GRADE_STRENGTH * 0.5)  # gentler on contrast
    warmth = (m[0] - m[2]) * gain
    shift = GRADE_STRENGTH * (TARGET_WARMTH - warmth) / 2         # +R/-B, or the reverse
    pivot = luma * gain
    exprs = []
    for c, off in zip("rgb", (shift, 0.0, -shift)):
        exprs.append(f"{c}='clip(({pivot:.2f}+(val*{gain:.4f}-{pivot:.2f})*{con:.4f})+{off:.2f},0,255)'")
    summary = (f"luma {luma:.0f}->{min(255, pivot):.0f}, warmth {m[0] - m[2]:.0f}->"
               f"{warmth + 2 * shift:.0f}, contrast x{con:.2f}")
    return "lutrgb=" + ":".join(exprs), summary


def render_clip(src, length, dst, log):
    """Graded, framed, 30fps video of one clip, held on its last frame up to `length`."""
    dur = duration(src)
    shots = find_shots(src, dur)
    rgb = frames(src)
    rate = len(rgb) / dur
    parts, labels = [], []
    for k, (a, b) in enumerate(shots):
        grade, summary = grade_for(rgb[int(a * rate):max(int(a * rate) + 1, int(b * rate))])
        log.append(f"    shot {a:4.2f}-{b:4.2f}s: {summary}")
        parts.append(f"[0:v]trim={a:.4f}:{b:.4f},setpts=PTS-STARTPTS,{grade}[p{k}]")
        labels.append(f"[p{k}]")
    hold = max(0.0, length - dur)
    fc = ";".join(parts) + ";" + "".join(labels) + (
        f"concat=n={len(shots)}:v=1:a=0,scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration={hold:.3f},"
        f"format=yuv420p[v]")
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]",
         "-t", f"{length:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "medium", dst])
    return hold


def loudnorm_measure(path, pre=""):
    af = (pre + "," if pre else "") + f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:print_format=json"
    err = run(["ffmpeg", "-v", "info", "-i", path, "-af", af, "-f", "null", "-"],
              capture_output=True, text=True).stderr
    return json.loads(err[err.rindex("{"):err.rindex("}") + 1])


def loudnorm_apply(m):
    return (f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:"
            f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
            f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")


def balanced(text, limit=CAPTION_MAX_CHARS):
    if len(text) <= limit:
        return [text]
    words = text.split()
    k = min(range(1, len(words)),
            key=lambda k: max(len(" ".join(words[:k])), len(" ".join(words[k:]))))
    lines = [" ".join(words[:k]), " ".join(words[k:])]
    assert max(map(len, lines)) <= limit + 2, f"caption too long for 2 lines: {text}"
    return lines


def esc(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=3)
    ap.add_argument("--words", required=True)
    ap.add_argument("-o", "--output", default="chickpeas_final.mp4")
    args = ap.parse_args()

    words = [c["words"] for c in json.load(open(args.words))]
    for cap, w in zip(CAPTIONS, words):
        assert sum(n for _, n in cap) == len(w), "caption word counts must match the transcript"
    n = len(args.clips)
    durs = [duration(c) for c in args.clips]

    # Clip lengths: whole clip, plus a held frame when the next clip's first word
    # would otherwise land inside the crossfade or right on this clip's last word.
    lengths = []
    for i in range(n):
        last_word = words[i][-1][2]
        if i < n - 1:
            need = last_word + GAP + FADE - words[i + 1][0][1]
        else:
            need = last_word + TAIL_MIN
        lengths.append(max(durs[i], need))
    starts = [0.0]
    for L in lengths[:-1]:
        starts.append(starts[-1] + L - FADE)
    total = starts[-1] + lengths[-1]

    tmp = tempfile.mkdtemp(prefix="chickpeas_")
    log = []

    # ---- video per clip
    vids = []
    for i, src in enumerate(args.clips):
        log.append(f"  clip {i + 1}: {durs[i]:.2f}s source, placed {starts[i]:.2f}-"
                   f"{starts[i] + lengths[i]:.2f}s")
        dst = os.path.join(tmp, f"v{i}.mp4")
        hold = render_clip(src, lengths[i], dst, log)
        if hold > 0:
            log.append(f"    last frame held {hold:.2f}s so the next line does not start mid-word")
        vids.append(dst)

    # ---- audio per clip: clean, then match loudness before mixing
    clean = "highpass=f=80,afftdn=nr=12:nf=-45:tn=1"
    auds = []
    for i, src in enumerate(args.clips):
        m = loudnorm_measure(src, clean)
        dst = os.path.join(tmp, f"a{i}.wav")
        fade_in = min(FADE, max(0.02, words[i][0][1] - 0.05)) if i else 0.0
        fade_out = (f",afade=t=out:st={lengths[i] - FADE:.3f}:d={FADE}" if i < n - 1 else
                    f",afade=t=out:st={lengths[i] - 0.25:.3f}:d=0.25")
        fin = f",afade=t=in:d={fade_in:.3f}" if fade_in else ""
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-af",
             f"{clean},{loudnorm_apply(m)},aresample=48000,apad=whole_dur={lengths[i]:.3f}"
             f"{fin}{fade_out}", "-ac", "2", "-ar", "48000", dst])
        log.append(f"  clip {i + 1} voice: {m['input_i']} LUFS -> {LUFS} (fade in {fade_in:.2f}s)")
        auds.append(dst)

    mix = os.path.join(tmp, "mix.wav")
    ins, fc = [], []
    for i, a in enumerate(auds):
        ins += ["-i", a]
        ms = int(round(starts[i] * 1000))
        fc.append(f"[{i}:a]adelay={ms}|{ms}[d{i}]")
    fc.append("".join(f"[d{i}]" for i in range(n)) +
              f"amix=inputs={n}:duration=longest:normalize=0,atrim=0:{total:.3f}[m]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[m]",
         "-ar", "48000", mix])
    final_audio = os.path.join(tmp, "final.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", mix, "-af", loudnorm_apply(loudnorm_measure(mix)),
         "-ar", "48000", final_audio])

    # ---- picture: crossfades, title, step labels, captions
    ins, fc = [], []
    for v in vids:
        ins += ["-i", v]
    ins += ["-i", final_audio]
    v = "[0:v]"
    for i in range(1, n):
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={FADE}:offset={starts[i]:.3f}[x{i}]")
        v = f"[x{i}]"

    def text(label, txt, size, y, t0, t1, extra=""):
        nonlocal v
        fc.append(f"{v}drawtext=fontfile={FONT}:text='{esc(txt)}':fontsize={size}:fontcolor=white:"
                  f"borderw={max(4, size // 13)}:bordercolor=black@0.9:shadowcolor=black@0.55:"
                  f"shadowx=3:shadowy=4:x=(w-text_w)/2:y={y}{extra}:"
                  f"enable='between(t,{t0:.3f},{t1:.3f})'[{label}]")
        v = f"[{label}]"

    # Title card, fading in and out inside the first two seconds.
    alpha = (f":alpha='if(lt(t,0.25),t/0.25,if(gt(t,{TITLE_SECONDS - 0.35}),"
             f"max(0,({TITLE_SECONDS}-t)/0.35),1))'")
    for j, line in enumerate(TITLE):
        text(f"t{j}", line, 150, f"h*0.36+{j * 165}-165", 0, TITLE_SECONDS, alpha)

    # STEP labels in the top safe area; they swap at the middle of each crossfade.
    for i, label in enumerate(STEPS[:n]):
        t0 = starts[i] + (FADE / 2 if i else 0)
        t1 = starts[i] + lengths[i] - (FADE / 2 if i < n - 1 else 0) - 1 / FPS
        text(f"s{i}", label, 56, "h*0.12", t0, t1,
             ":box=1:boxcolor=black@0.35:boxborderw=20")

    # Captions: each shown from its first word until the next caption starts
    # (or 0.5s after its last word), never overlapping.
    caps = []
    for i, cap in enumerate(CAPTIONS):
        k = 0
        for txt, cnt in cap:
            seg = words[i][k:k + cnt]
            caps.append((txt, starts[i] + seg[0][1], starts[i] + seg[-1][2]))
            k += cnt
    for c, (txt, a, b) in enumerate(caps):
        end = b + 0.5
        if c + 1 < len(caps):
            end = min(end, caps[c + 1][1] - 1 / FPS)
        lines = balanced(txt)
        top = f"h*{CAPTION_Y}-{(len(lines) - 1) * CAPTION_STEP // 2}-{CAPTION_SIZE // 2}"
        for j, line in enumerate(lines):
            text(f"c{c}_{j}", line, CAPTION_SIZE, f"{top}+{j * CAPTION_STEP}", a, end)

    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc),
         "-map", v, "-map", f"{n}:a", "-t", f"{total:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.output])

    print("\n".join(log))
    print("captions:")
    for txt, a, b in caps:
        print(f"  {a:6.2f}-{b:6.2f}  {txt}")
    print(f"wrote {args.output} ({total:.2f}s)")


if __name__ == "__main__":
    main()
