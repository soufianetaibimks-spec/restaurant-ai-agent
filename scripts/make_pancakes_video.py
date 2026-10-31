#!/usr/bin/env python3
"""Build the 24-second vertical Cottage Cheese Pancakes short from three narrated clips.

Same edit as make_tuscan_chicken_video.py (24s exactly, voice-over laid end to
end, 0.3s dissolves centred on the audio joins, cooking sound slightly lower
under the voice, one warm grade), plus:

  * a soft acoustic bed from make_acoustic_bed.py, low under the voice and
    dipping further while she speaks;
  * text cards with colour emoji, rendered here as transparent PNGs (Poppins
    Bold + Noto Color Emoji, white with a soft shadow) because ffmpeg's
    drawtext cannot draw colour emoji;
  * the site address as the end frame instead of the small brand mark.

Usage:
    python3 scripts/make_pancakes_video.py blend.mp4 cook.mp4 serve.mp4 \
        --words scripts/pancakes_words.json --font Poppins-Bold.ttf \
        --spleeter DIR --music bed.wav -o pancakes_final.mp4
"""
import argparse
import os
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import make_tuscan_chicken_video as edit

EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_STRIKE = 109          # Noto Color Emoji is a bitmap font with one size
W, H = edit.W, edit.H

# (lines, start, end, size, top as a fraction of the height, fade in, fade out)
CARDS = [
    (["Cottage Cheese", "Pancakes \U0001F95E"], 0.0, 4.5, 96, 0.10, 0.0, 0.3),
    (["No Flour • No Protein Powder"], 8.3, 13.0, 56, 0.12, 0.3, 0.3),
    (["26g Protein ✨", "Recipe on the blog"], 16.3, 21.6, 68, 0.11, 0.3, 0.3),
    (["thespoonandhearth.com"], 21.8, 24.0, 64, 0.12, 0.3, 0.0),
]
MUSIC_LEVEL_DB, MUSIC_DIP_DB = -18.0, 6.0


def is_emoji(ch):
    return ord(ch) >= 0x2600 and ch != "•"


def emoji_image(ch, size):
    font = ImageFont.truetype(EMOJI_FONT, EMOJI_STRIKE)
    im = Image.new("RGBA", (EMOJI_STRIKE * 2, EMOJI_STRIKE * 2))
    ImageDraw.Draw(im).text((0, 0), ch, font=font, embedded_color=True)
    im = im.crop(im.getbbox())
    h = int(size * 0.95)
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def runs(line):
    out, cur = [], ""
    for ch in line:
        if is_emoji(ch):
            if cur:
                out.append(("t", cur))
                cur = ""
            out.append(("e", ch))
        else:
            cur += ch
    return out + ([("t", cur)] if cur else [])


def render_card(lines, size, top, font_path, path):
    """Full-frame transparent PNG with the lines centred, white with a soft shadow."""
    font = ImageFont.truetype(font_path, size)
    text = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(text)
    stroke = max(2, size // 22)
    widest = 0
    for j, line in enumerate(lines):
        parts = [(k, s, emoji_image(s, size) if k == "e" else None) for k, s in runs(line)]
        widths = [img.width if k == "e" else font.getlength(s) for k, s, img in parts]
        x = (W - sum(widths)) / 2
        widest = max(widest, sum(widths))
        baseline = int(H * top + size * (0.95 + 1.18 * j))
        for (k, s, img), w in zip(parts, widths):
            if k == "e":
                text.alpha_composite(img, (int(x), int(baseline - size * 0.36 - img.height / 2)))
            else:
                draw.text((x, baseline), s, font=font, fill="white", anchor="ls",
                          stroke_width=stroke, stroke_fill=(0, 0, 0, 110))
            x += w
    assert widest <= 880, f"card too wide ({widest:.0f}px): {lines}"
    alpha = text.getchannel("A")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: a * 0.6).filter(ImageFilter.GaussianBlur(7)))
    card = Image.new("RGBA", (W, H))
    card.alpha_composite(shadow, (3, 6))
    card.alpha_composite(text)
    card.save(path)
    return widest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--font")
    ap.add_argument("--music", required=True)
    known, rest = ap.parse_known_args()
    tmp = tempfile.mkdtemp(prefix="pancake_cards_")
    edit.IMAGE_CARDS = []
    for k, (lines, t0, t1, size, top, fade_in, fade_out) in enumerate(CARDS):
        png = os.path.join(tmp, f"card{k}.png")
        wide = render_card(lines, size, top, known.font, png)
        print(f"card {k + 1}: {' / '.join(lines)}  ({wide:.0f}px, {t0:.1f}-{t1:.1f}s)")
        edit.IMAGE_CARDS.append((png, t0, t1, fade_in, fade_out))
    edit.HOOK, edit.TEXTS, edit.MARK = None, [], None
    edit.CLIP_SECONDS = 8.0  # clips run 8.043s; their last 0.04s is silent
    edit.MUSIC = (known.music, MUSIC_LEVEL_DB, MUSIC_DIP_DB)
    sys.argv = [sys.argv[0], *rest, "--font", known.font]
    if "-o" not in sys.argv and "--output" not in sys.argv:
        sys.argv += ["-o", "pancakes_final.mp4"]
    edit.main()
