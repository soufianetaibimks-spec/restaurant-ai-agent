#!/usr/bin/env python3
"""Build the 24-second vertical Egg Roll in a Bowl short from three narrated clips.

Same edit as make_tuscan_chicken_video.py (24s exactly, voice-over laid end to
end untouched, 0.3s dissolves centred on the audio joins, cooking sound
slightly lower under the voice, one warm grade, Spoon & Hearth mark on the
final bite). Only the on-screen text differs: the first card is the big hook,
on screen from the very first frame.

Usage:
    python3 scripts/make_egg_roll_bowl_video.py turkey.mp4 cabbage.mp4 serve.mp4 \
        --words scripts/egg_roll_bowl_words.json --font Poppins-Bold.ttf \
        --spleeter DIR -o egg_roll_bowl_final.mp4
"""
import sys

import make_tuscan_chicken_video as edit

edit.HOOK = (["Egg rolls…", "but HEALTHY?"], 0.0, 3.0, 104, 0.12)
edit.TEXTS = [
    ("1 bag of coleslaw mix\n= no chopping", 8.0, 11.0, 64),
    ("35g protein\nlow-carb • 25 min", 18.0, 22.0, 64),
]

if __name__ == "__main__":
    if "-o" not in sys.argv and "--output" not in sys.argv:
        sys.argv += ["-o", "egg_roll_bowl_final.mp4"]
    edit.main()
