#!/usr/bin/env python3
"""Whisper large-v3-turbo по всем out/<модель>/meta.csv → out/<модель>/asr.csv (asr, cer к обычному тексту).
CER показывает разборчивость; ударение и долготу Whisper не проверяет — это экспертиза на слух.
  python3 tts_eval/asr.py out
"""
import csv
import glob
import os
import re
import sys
import time
import unicodedata

import jiwer
import librosa
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

LANG = {"it": "italian", "ru": "russian", "he": "hebrew"}
MODEL = "openai/whisper-large-v3-turbo"


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ё", "е").replace("’", "'")
    s = re.sub(r"[^\w' ]+", " ", s)
    return " ".join(s.split())


def main(root):
    import json
    ref = {x["id"]: x["inputs"]["plain"] for x in json.load(open(os.path.join(os.path.dirname(__file__), "testset.json")))}
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    proc = WhisperProcessor.from_pretrained(MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL, torch_dtype=dtype).to(dev).eval()
    for meta in sorted(glob.glob(f"{root}/*/meta.csv")):
        d = os.path.dirname(meta)
        out = f"{d}/asr.csv"
        rows = [r for r in csv.DictReader(open(meta)) if r["wav"]]
        done = {(r["id"], r["variant"]): r for r in csv.DictReader(open(out))} if os.path.exists(out) else {}
        t0 = time.time()
        for r in rows:
            k = (r["id"], r["variant"])
            if k in done:
                r.update(asr=done[k]["asr"], cer=done[k]["cer"])
                continue
            y, _ = librosa.load(f"{d}/{r['wav']}", sr=16000)
            feats = proc(y, sampling_rate=16000, return_tensors="pt").input_features.to(dev, dtype)
            with torch.inference_mode():
                ids = model.generate(feats, language=LANG[r["lang"]], task="transcribe")
            r["asr"] = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
            r["cer"] = round(jiwer.cer(norm(ref[r["id"]]), norm(r["asr"]) or "-"), 3)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{d}: {len(rows)} записей, {time.time() - t0:.0f} с", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
