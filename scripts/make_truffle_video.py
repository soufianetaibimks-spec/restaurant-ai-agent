#!/usr/bin/env python3
"""Build the vertical chocolate-truffle video.

Merges five clips (in the order given) into one 1080x1920 video with short
crossfades, adds an en-US-JennyNeural voiceover (edge-tts), one sentence per
clip, ducks the original audio to 20% while the voice speaks, and burns each
sentence in as an on-screen caption.

A clip may also be a still image; it is shown for CLIP_SECONDS with a slow zoom.

Usage:
    python3 scripts/make_truffle_video.py cutting.mp4 processor.mp4 \
        rolling.mp4 holding.mp4 breaking.mp4 -o final.mp4

If edge-tts cannot reach its server, the video is still built (with captions,
fades and original audio) and a warning is printed. Pass --no-voice to skip it.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile

W, H, FPS = 1080, 1920, 30
FADE = 0.5           # crossfade length between clips (s)
CLIP_SECONDS = 10.0  # length used for still images
VOICE = "en-US-JennyNeural"
VOICE_DELAY = 0.8    # voice starts this long after its clip begins (s)
DUCK = 0.2           # original-audio level while the voice speaks
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SENTENCES = [
    "Start by chopping your ingredients.",
    "Blend everything until smooth.",
    "Roll the mixture into small balls.",
    "Perfectly round and ready.",
    "Break one open and enjoy!",
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


def normalize(src, dst):
    """Re-encode one clip to 1080x1920@30fps with a stereo 48k audio track."""
    fit = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
           f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p")
    if os.path.splitext(src)[1].lower() in IMAGE_EXTS:
        frames = int(CLIP_SECONDS * FPS)
        vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
              f"zoompan=z='1+0.08*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", src,
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-vf", vf, "-t", str(CLIP_SECONDS), "-map", "0:v", "-map", "1:a",
             "-c:v", "libx264", "-crf", "18", "-preset", "medium",
             "-c:a", "aac", "-b:a", "192k", "-shortest", dst])
        return
    _, has_audio = probe(src)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src]
    if has_audio:
        amap = ["-map", "0:a:0"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = ["-map", "1:a", "-shortest"]
    run(cmd + ["-vf", fit, "-map", "0:v:0", *amap, "-af", "aresample=48000",
               "-ac", "2", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", dst])


async def _tts(out_dir):
    import edge_tts
    paths = []
    for i, text in enumerate(SENTENCES, 1):
        p = os.path.join(out_dir, f"voice{i}.mp3")
        await edge_tts.Communicate(text, VOICE, proxy=os.environ.get("HTTPS_PROXY")).save(p)
        paths.append(p)
    return paths


def make_voice(out_dir):
    try:
        paths = asyncio.run(_tts(out_dir))
    except Exception as e:  # network blocked, edge-tts missing, ...
        print(f"WARNING: voiceover skipped, edge-tts failed: {e!r}", file=sys.stderr)
        return None
    return paths


def caption_escape(text):
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")


def wrap(text, max_chars=22):
    """Split a caption into at most two balanced lines."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    best = min(range(1, len(words)),
               key=lambda k: abs(len(" ".join(words[:k])) - len(" ".join(words[k:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs=5, help="five clips in final order")
    ap.add_argument("-o", "--output", default="final.mp4")
    ap.add_argument("--no-voice", action="store_true")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="truffle_")
    norm = []
    for i, src in enumerate(args.clips):
        dst = os.path.join(tmp, f"clip{i}.mp4")
        normalize(src, dst)
        norm.append(dst)
    durs = [probe(p)[0] for p in norm]
    starts = [0.0]
    for d in durs[:-1]:
        starts.append(starts[-1] + d - FADE)
    total = starts[-1] + durs[-1]

    voices = None if args.no_voice else make_voice(tmp)

    inputs = []
    for p in norm:
        inputs += ["-i", p]
    if voices:
        for p in voices:
            inputs += ["-i", p]

    fc = []
    # Crossfade video and audio clip by clip.
    v, a = "[0:v]", "[0:a]"
    for i in range(1, len(norm)):
        fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={FADE}:offset={starts[i]:.3f}[v{i}]")
        fc.append(f"{a}[{i}:a]acrossfade=d={FADE}[a{i}]")
        v, a = f"[v{i}]", f"[a{i}]"

    # Captions: one per clip, centred in the lower third, wrapped to two lines.
    for i, text in enumerate(SENTENCES):
        t0 = starts[i] + (FADE if i else 0.2)
        t1 = starts[i] + durs[i] - (FADE if i < len(norm) - 1 else 0.2)
        for j, line in enumerate(wrap(text)):
            fc.append(
                f"{v}drawtext=fontfile={FONT}:text='{caption_escape(line)}':fontsize=72:"
                f"fontcolor=white:borderw=5:bordercolor=black@0.85:"
                f"shadowcolor=black@0.5:shadowx=3:shadowy=3:"
                f"x=(w-text_w)/2:y=h*0.74+{j * 96}:enable='between(t,{t0:.3f},{t1:.3f})'"
                f"[c{i}_{j}]")
            v = f"[c{i}_{j}]"

    if voices:
        windows = []
        for i, p in enumerate(voices):
            start = starts[i] + VOICE_DELAY
            dur = probe(p)[0]
            windows.append((start, start + dur))
            ms = int(start * 1000)
            fc.append(f"[{len(norm) + i}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"adelay={ms}|{ms},apad[vo{i}]")
        cond = "+".join(f"between(t,{s - 0.15:.3f},{e + 0.15:.3f})" for s, e in windows)
        fc.append(f"{a}volume='if({cond},{DUCK},1)':eval=frame[bg]")
        vo = "".join(f"[vo{i}]" for i in range(len(voices)))
        fc.append(f"[bg]{vo}amix=inputs={len(voices) + 1}:duration=first:normalize=0[aout]")
        a = "[aout]"

    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
         "-map", v, "-map", a, "-t", f"{total:.3f}",
         "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.output])
    print(f"wrote {args.output} ({total:.1f}s, voiceover: {'yes' if voices else 'NO'})")


if __name__ == "__main__":
    main()
