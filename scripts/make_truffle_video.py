#!/usr/bin/env python3
"""Build the vertical avocado chocolate-truffle video.

Five shots, each paired with one voiceover line (edge-tts, en-US-JennyNeural):
every clip is cut to the length of its line (trimmed, or slowed down slightly
when the voice is longer than the footage), scaled to 1080x1920, joined with
short crossfades, captioned with its line, and mixed with the voice while the
original audio sits at 15% under it.

A shot may also be a still image; it is shown with a slow zoom.

Usage:
    python3 scripts/make_truffle_video.py hook.mp4 board.mp4 processor.mp4 \
        rolling.mp4 bite.mp4 -o final.mp4

Voice files recorded elsewhere (e.g. ElevenLabs) can be passed in shot order
with --voices; edge-tts is then skipped.

If edge-tts cannot reach its server, the video is still built with estimated
line lengths, captions and fades but no voice, and a warning is printed.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile

W, H, FPS = 1080, 1920, 30
FADE = 0.4          # crossfade between shots (s)
LEAD = 0.3          # silence before the line, after the incoming fade (s)
TAIL = 0.5          # pause after the line, before the outgoing fade (s)
MAX_SLOWDOWN = 1.35  # never stretch footage more than this
VOICE = "en-US-JennyNeural"
DUCK = 0.15         # original-audio level under the voice
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# (line, where the trimmed window sits in the source clip)
#   ("start", t): window begins at t seconds
#   ("end", t):   window ends at t seconds
SHOTS = [
    ("Zero sugar... and you'll never guess the secret ingredient.", ("start", 5.0)),
    ("Ripe avocado, a few dates, and raw cocoa. That's it.", ("start", 3.0)),
    ("One minute in the processor... and the green completely disappears.", ("end", 7.0)),
    ("Roll them, coat them in cocoa, and chill for 30 minutes.", ("start", 1.5)),
    ("Silky, fudgy, pure chocolate. Save this before you lose it!", ("start", 0.0)),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def run(cmd):
    subprocess.run(cmd, check=True)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
         "-of", "json", path], check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    return (float(info["format"].get("duration", 0) or 0),
            any(s["codec_type"] == "audio" for s in info["streams"]))


async def _tts(out_dir):
    import edge_tts
    paths = []
    for i, (text, _) in enumerate(SHOTS, 1):
        p = os.path.join(out_dir, f"voice{i}.mp3")
        await edge_tts.Communicate(text, VOICE, proxy=os.environ.get("HTTPS_PROXY")).save(p)
        paths.append(p)
    return paths


def make_voice(out_dir):
    try:
        return asyncio.run(_tts(out_dir))
    except Exception as e:  # network blocked, edge-tts missing, ...
        print(f"WARNING: voiceover skipped, edge-tts failed: {e!r}", file=sys.stderr)
        return None


def estimate_speech(text):
    """Rough Jenny speaking time, used only when no voice file exists."""
    return len(text.split()) / 2.7 + 0.4 * text.count("...") + 0.25 * text.count(".")


def render_shot(src, window, length, dst):
    """Cut `length` seconds of `src` at `window`, at 1080x1920@30 with stereo audio."""
    if os.path.splitext(src)[1].lower() in IMAGE_EXTS:
        frames = int(round(length * FPS))
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", src,
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-vf", vf, "-t", f"{length:.3f}", "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-c:a", "aac", "-b:a", "192k", dst])
        return 1.0

    dur, has_audio = probe(src)
    mode, t = window
    # Footage available for this shot, then how much it must be stretched.
    if mode == "end":
        avail = min(t, dur)
        speed = max(1.0, length / avail)
        start = max(0.0, avail - length / speed)
    else:
        start = min(t, dur)
        avail = dur - start
        speed = max(1.0, length / avail)
        if speed > MAX_SLOWDOWN:  # pull the window earlier rather than over-stretch
            start = max(0.0, dur - length / MAX_SLOWDOWN)
            speed = max(1.0, length / (dur - start))
    src_len = length / speed

    fit = (f"setpts={speed:.5f}*(PTS-STARTPTS),scale={W}:{H}:force_original_aspect_ratio=increase,"
           f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{src_len:.3f}", "-i", src]
    if has_audio:
        af = f"aresample=48000,atempo={1 / speed:.5f},apad"
        amap = ["-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        af = "aresample=48000"
        amap = ["-map", "1:a"]
    run(cmd + ["-vf", fit, "-af", af, "-map", "0:v:0", *amap, "-ac", "2",
               "-t", f"{length:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", dst])
    return speed


def wrap(text, max_chars=20):
    """Greedy word wrap for captions."""
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur]


def caption_escape(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=len(SHOTS), help="clips in shot order")
    ap.add_argument("-o", "--output", default="final.mp4")
    ap.add_argument("--voices", nargs=len(SHOTS), metavar="AUDIO",
                    help="pre-recorded voice files in shot order (skips edge-tts)")
    ap.add_argument("--no-voice", action="store_true")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="truffle_")
    if args.voices:
        voices = args.voices
    else:
        voices = None if args.no_voice else make_voice(tmp)
    speech = ([probe(p)[0] for p in voices] if voices
              else [estimate_speech(text) for text, _ in SHOTS])

    n = len(SHOTS)
    # Each shot holds its line plus breathing room, plus the fades it shares.
    lengths = [LEAD + s + TAIL + (FADE if i else 0) + (FADE if i < n - 1 else 0)
               for i, s in enumerate(speech)]
    starts = [0.0]
    for d in lengths[:-1]:
        starts.append(starts[-1] + d - FADE)
    total = starts[-1] + lengths[-1]
    speech_at = [starts[i] + (FADE if i else 0) + LEAD for i in range(n)]

    shots = []
    for i, (src, (text, window)) in enumerate(zip(args.clips, SHOTS)):
        dst = os.path.join(tmp, f"shot{i}.mp4")
        speed = render_shot(src, window, lengths[i], dst)
        print(f"shot {i + 1}: {lengths[i]:.2f}s"
              + (f" (slowed {speed:.2f}x)" if speed > 1.001 else ""))
        shots.append(dst)

    inputs = []
    for p in shots + (voices or []):
        inputs += ["-i", p]

    fc = []
    v, a = "[0:v]", "[0:a]"
    for i in range(1, n):
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={FADE}:offset={starts[i]:.3f}[v{i}]")
        fc.append(f"{a}[{i}:a]acrossfade=d={FADE}[a{i}]")
        v, a = f"[v{i}]", f"[a{i}]"

    # Bold, centred captions in the lower-middle of the frame, shown while the
    # shot is fully on screen.
    size, step = 76, 98
    for i, (text, _) in enumerate(SHOTS):
        t0 = starts[i] + (FADE if i else 0.1)
        t1 = starts[i] + lengths[i] - (FADE if i < n - 1 else 0.1)
        lines = wrap(text)
        top = f"h*0.70-{(len(lines) - 1) * step // 2}"
        for j, line in enumerate(lines):
            fc.append(
                f"{v}drawtext=fontfile={FONT}:text='{caption_escape(line)}':fontsize={size}:"
                f"fontcolor=white:borderw=6:bordercolor=black@0.9:"
                f"shadowcolor=black@0.6:shadowx=3:shadowy=4:"
                f"x=(w-text_w)/2:y={top}+{j * step}:enable='between(t,{t0:.3f},{t1:.3f})'"
                f"[c{i}_{j}]")
            v = f"[c{i}_{j}]"

    if voices:
        windows = []
        for i, s in enumerate(speech):
            windows.append((speech_at[i], speech_at[i] + s))
            ms = int(speech_at[i] * 1000)
            fc.append(f"[{n + i}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"adelay={ms}|{ms},apad[vo{i}]")
        cond = "+".join(f"between(t,{s - 0.2:.3f},{e + 0.2:.3f})" for s, e in windows)
        fc.append(f"{a}volume='if({cond},{DUCK},1)':eval=frame[bg]")
        vo = "".join(f"[vo{i}]" for i in range(n))
        fc.append(f"[bg]{vo}amix=inputs={n + 1}:duration=first:normalize=0[aout]")
        a = "[aout]"

    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", v, "-map", a, "-t", f"{total:.3f}",
         "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.output])
    print(f"wrote {args.output} ({total:.1f}s, voiceover: "
          f"{'yes' if voices else 'NO - shot lengths are estimates'})")


if __name__ == "__main__":
    main()
