#!/usr/bin/env python3
"""Transcribe clips and get word timestamps, fully offline.

Text comes from Whisper small.en (sherpa-onnx); word timings come from forcing
that text onto the audio with PocketSphinx. Whisper's text is normalised for
the aligner (numbers spelled out, contractions expanded, "chickpeas" split),
so the aligned words are lower-case dictionary words, not display text.

Usage:
    python3 scripts/transcribe_clips.py --model DIR clip1.mp4 clip2.mp4 ... -o words.json

DIR is an extracted sherpa-onnx-whisper-small.en release, e.g. from
https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
"""
import argparse
import json
import os
import re
import subprocess

import numpy as np

NUMBERS = {"11": "eleven", "400": "four hundred", "200": "two hundred", "30": "thirty",
           "25": "twenty five"}
EXPAND = {"they're": "they are", "you're": "you are", "it's": "it is", "that's": "that is",
          "chickpeas": "chick peas", "chickpea": "chick pea"}


def pcm16k(path):
    return subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ar", "16000", "-ac", "1",
                           "-f", "s16le", "-"], check=True, capture_output=True).stdout


def for_aligner(text):
    words = []
    for w in re.findall(r"[\w']+", text.lower()):
        w = NUMBERS.get(w, EXPAND.get(w, w))
        words.extend(w.split())
    return " ".join(words)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--model", required=True)
    ap.add_argument("-o", "--output", default="words.json")
    args = ap.parse_args()

    import sherpa_onnx
    from pocketsphinx import Decoder

    m = args.model
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=f"{m}/small.en-encoder.onnx", decoder=f"{m}/small.en-decoder.onnx",
        tokens=f"{m}/small.en-tokens.txt", language="en", task="transcribe", num_threads=4)
    aligner = Decoder()

    out = []
    for clip in args.clips:
        raw = pcm16k(clip)
        stream = rec.create_stream()
        stream.accept_waveform(16000, np.frombuffer(raw, np.int16).astype(np.float32) / 32768)
        rec.decode_stream(stream)
        text = stream.result.text.strip()

        aligner.set_align_text(for_aligner(text))
        aligner.start_utt()
        aligner.process_raw(raw, full_utt=True)
        aligner.end_utt()
        words = [(re.sub(r"\(\d+\)$", "", s.word), s.start_frame / 100, (s.end_frame + 1) / 100)
                 for s in aligner.seg() if s.word not in ("<s>", "</s>", "<sil>")]
        out.append({"clip": os.path.basename(clip), "text": text, "words": words})
        print(f"{clip}\n  {text}\n  " + "  ".join(f"{w}[{a:.2f}-{b:.2f}]" for w, a, b in words))

    with open(args.output, "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
