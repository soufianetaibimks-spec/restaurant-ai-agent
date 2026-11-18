#!/usr/bin/env python3
"""Build the 24-second vertical Protein Banana Bread short from three narrated clips.

Same edit as make_pancakes_video.py (24s exactly, voice-over laid end to end,
0.3s dissolves centred on the joins, cooking sound slightly lower under the
voice and handed over smoothly at the joins, per-channel levels grade, soft
acoustic bed). Differences: the site address stays small at the top for the
whole video, the last card holds to the end, and there is no end frame.

Clip 1's voice-over starts with a false start ("Protein, protein banana
bread"); the first "protein" is removed from the separated voice only, so the
video opens on "Protein banana bread" with a natural 0.25s lead-in.

Usage:
    python3 scripts/make_banana_bread_video.py mash.mp4 bake.mp4 slice.mp4 \
        --words scripts/banana_bread_words.json --font Poppins-Bold.ttf \
        --spleeter DIR --music bed.wav -o banana_bread_final.mp4
"""
import make_pancakes_video as pancakes

# (lines, start, end, size, top as a fraction of the height, fade in, fade out)
CARDS = [
    (["thespoonandhearth.com"], 0.0, 24.0, 36, 0.035, 0.0, 0.0),  # small, whole video
    (["Protein", "Banana Bread"], 0.0, 3.0, 96, 0.085, 0.0, 0.3),
    (["No Flour · No Added Sugar"], 8.0, 11.0, 60, 0.105, 0.3, 0.3),
    (["11g Protein Per Slice"], 16.0, 24.0, 60, 0.105, 0.3, 0.0),
]

if __name__ == "__main__":
    pancakes.edit.VOICE_CUTS = {0: [(0.02, 0.97)]}
    pancakes.edit.VOICE_MATCH = True  # clip 2's voice was recorded ~4 dB softer
    pancakes.run(CARDS, "banana_bread_final.mp4")
