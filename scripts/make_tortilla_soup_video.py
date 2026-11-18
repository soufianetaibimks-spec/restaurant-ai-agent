#!/usr/bin/env python3
"""Build the 24-second vertical Healthy Chicken Tortilla Soup short from three narrated clips.

Same edit as make_tuscan_chicken_video.py (24s exactly, voice-over laid end to
end untouched, 0.3s dissolves centred on the audio joins, cooking sound
slightly lower under the voice, one warm grade, Spoon & Hearth mark on the
final spoon bite). Only the on-screen text differs: the first card is the big
hook, on screen from the very first frame.

Usage:
    python3 scripts/make_tortilla_soup_video.py spices.mp4 simmer.mp4 serve.mp4 \
        --words scripts/tortilla_soup_words.json --font Poppins-Bold.ttf \
        --spleeter DIR -o tortilla_soup_final.mp4
"""
import sys

import make_tuscan_chicken_video as edit

edit.HOOK = (["Healthy chicken", "tortilla soup"], 0.0, 3.0, 96, 0.12)
# The lime squeeze and the spoon bite are one continuous shot; the bite starts here.
edit.MARK_FROM = 5.42
edit.TEXTS = [
    ("One pot,\nno cream, no frying", 8.0, 11.0, 64),
    ("35g protein • 40 min\nfreezer-friendly", 18.0, 22.0, 64),
]

if __name__ == "__main__":
    if "-o" not in sys.argv and "--output" not in sys.argv:
        sys.argv += ["-o", "tortilla_soup_final.mp4"]
    edit.main()
