#!/usr/bin/env python3
"""Build the 24-second vertical Healthy Mashed Potatoes short from three narrated clips.

Same edit as make_banana_bread_video.py (24s exactly, voice-over laid end to
end, 0.3s dissolves centred on the joins, cooking sound slightly lower under
the voice and handed over smoothly at the joins, per-channel levels grade,
voice level matched across clips, site address small at the top throughout,
last card held to the end). The music is the "autumn" style of
make_acoustic_bed.py.

Usage:
    python3 scripts/make_acoustic_bed.py --seconds 24 --style autumn -o autumn_bed.wav
    python3 scripts/make_mashed_potatoes_video.py mash.mp4 mixins.mp4 serve.mp4 \
        --words scripts/mashed_potatoes_words.json --font Poppins-Bold.ttf \
        --spleeter DIR --music autumn_bed.wav -o mashed_potatoes_final.mp4
"""
import make_pancakes_video as pancakes

# (lines, start, end, size, top as a fraction of the height, fade in, fade out)
CARDS = [
    (["thespoonandhearth.com"], 0.0, 24.0, 36, 0.035, 0.0, 0.0),  # small, whole video
    (["Healthy", "Mashed Potatoes"], 0.0, 3.0, 90, 0.085, 0.0, 0.3),
    (["No Butter · No Cream"], 8.0, 11.0, 60, 0.105, 0.3, 0.3),
    # one line would be 993px at 60pt; the line break stands in for the "·"
    (["11g Protein", "Thanksgiving Ready"], 16.0, 24.0, 60, 0.105, 0.3, 0.0),
]

if __name__ == "__main__":
    pancakes.edit.VOICE_MATCH = True
    # Clip 1's first shot (0-1.46s, colander over the sink) has potato pieces falling
    # through the colander. Drop it and play the next shot (tipping into the pot) at
    # half speed, so the mashing from 2.92s on stays in sync with its sound.
    pancakes.edit.PICTURE_REMAP = {0: [(1.46, 2.92, 2.0), (2.92, 8.0, 1.0)]}
    pancakes.run(CARDS, "mashed_potatoes_final.mp4")
