#!/usr/bin/env python3
"""Build the 24-second vertical Healthy Game Day Chili short from three narrated clips.

Same edit as make_tuscan_chicken_video.py (24s exactly, voice-over laid end to
end, 0.3s dissolves centred on the audio joins, cooking sound slightly lower
under the voice, one warm grade, Spoon & Hearth mark on the final spoon bite),
with its own hook and cards.

Clip 3's voice-over says "39 grams of protein" twice. The repeat (and the
pause before it) is removed from the separated voice only, keeping her
natural 0.34s pause before "One pot"; the cooking sound and picture are
untouched.

Usage:
    python3 scripts/make_turkey_chili_video.py turkey.mp4 simmer.mp4 serve.mp4 \
        --words scripts/turkey_chili_words.json --font Poppins-Bold.ttf \
        --spleeter DIR -o turkey_chili_final.mp4
"""
import sys

import make_tuscan_chicken_video as edit

edit.HOOK = (["Healthy", "game day chili"], 0.0, 3.0, 104, 0.12)
edit.TEXTS = [
    ("Lean turkey +\n2 kinds of beans", 8.0, 11.0, 64),
    ("39g protein • 1 pot • 45 min", 18.0, 22.0, 60),
]
edit.VOICE_CUTS = {2: [(1.90, 3.60)]}
edit.CLIP_SECONDS = 8.0  # clips 1-2 run 8.043s; their last 0.04s is silent

if __name__ == "__main__":
    if "-o" not in sys.argv and "--output" not in sys.argv:
        sys.argv += ["-o", "turkey_chili_final.mp4"]
    edit.main()
