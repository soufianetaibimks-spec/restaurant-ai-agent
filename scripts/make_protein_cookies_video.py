#!/usr/bin/env python3
"""Build the 24-second vertical Protein Cookies short from three narrated clips.

Same edit as make_pancakes_video.py (24s exactly, voice-over laid end to end,
0.3s dissolves centred on the joins, cooking sound slightly lower under the
voice and handed over smoothly at the joins, per-channel levels grade, soft
acoustic bed, colour-emoji text cards, site address as the end frame).

Usage:
    python3 scripts/make_protein_cookies_video.py dough.mp4 bake.mp4 break.mp4 \
        --words scripts/protein_cookies_words.json --font Poppins-Bold.ttf \
        --spleeter DIR --music bed.wav -o protein_cookies_final.mp4
"""
import make_pancakes_video as pancakes

# (lines, start, end, size, top as a fraction of the height, fade in, fade out)
CARDS = [
    (["Protein", "Cookies \U0001F36A"], 0.0, 4.5, 96, 0.10, 0.0, 0.3),
    # every card after the hook shares one size and one height
    (["No Flour • No Added Sugar"], 8.3, 13.0, 60, 0.12, 0.3, 0.3),
    (["8g Protein Each ✨", "Recipe on the blog"], 16.3, 21.6, 60, 0.12, 0.3, 0.3),
    (["thespoonandhearth.com"], 21.8, 24.0, 60, 0.12, 0.3, 0.0),
]

if __name__ == "__main__":
    pancakes.run(CARDS, "protein_cookies_final.mp4")
