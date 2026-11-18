#!/usr/bin/env python3
"""Build the 24-second vertical Starbucks-style Egg Bites short from three narrated clips.

Same edit as make_mashed_potatoes_video.py (24s exactly, voice-over laid end to
end, 0.3s dissolves centred on the joins, cooking sound slightly lower under
the voice and handed over smoothly at the joins, per-channel levels grade,
voice level matched across clips, site address small at the top throughout,
last card held to the end), with the default "bright" acoustic bed.

Clip 3's final shot (7.46-8.0s, the melty close-up) has the site address burned
in by the generator, in a serif font, at the lower right. It is zoomed 1.3x
toward the top of the frame so that text falls out of view and only the
Poppins address at the top remains.

Usage:
    python3 scripts/make_acoustic_bed.py --seconds 24 -o bed.wav
    python3 scripts/make_egg_bites_video.py blend.mp4 bake.mp4 serve.mp4 \
        --words scripts/egg_bites_words.json --font Poppins-Bold.ttf \
        --spleeter DIR --music bed.wav -o egg_bites_final.mp4
"""
import make_pancakes_video as pancakes

# (lines, start, end, size, top as a fraction of the height, fade in, fade out)
CARDS = [
    (["thespoonandhearth.com"], 0.0, 24.0, 36, 0.035, 0.0, 0.0),  # small, whole video
    (["Starbucks", "Egg Bites at Home"], 0.0, 3.0, 90, 0.085, 0.0, 0.3),
    (["Secret: Cottage Cheese"], 8.0, 11.0, 60, 0.105, 0.3, 0.3),
    (["16g Protein · No Sous Vide"], 16.0, 24.0, 60, 0.105, 0.3, 0.0),
]

if __name__ == "__main__":
    pancakes.edit.VOICE_MATCH = True
    # clip 3, shot by shot; the last shot zoomed in to hide the burned-in address
    pancakes.edit.PICTURE_REMAP = {2: [
        (0.0, 0.958, 1.0), (0.958, 2.917, 1.0), (2.917, 6.458, 1.0), (6.458, 7.458, 1.0),
        (7.458, 8.0, 1.0, (1.3, 0.5, 0.0)),
    ]}
    pancakes.run(CARDS, "egg_bites_final.mp4")
