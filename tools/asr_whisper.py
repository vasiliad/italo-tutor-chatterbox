#!/usr/bin/env python3
"""Распознавание записей Whisper large-v3-turbo и CER — отдельно от ноутбука.

transformers 5.x ломает pipeline("automatic-speech-recognition") на входе-словаре (KeyError 'num_frames'),
поэтому зовём модель напрямую. Дописывает в results.csv колонки asr и cer.

  python3 tools/asr_whisper.py results/2026-09-28_v3
"""
import csv
import re
import sys
import time
import unicodedata

import jiwer
import librosa
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

LANG = {"it": "italian", "ru": "russian", "ru+it": "russian", "he": "hebrew"}
MODEL = "openai/whisper-large-v3-turbo"


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # знаки ударения и огласовки
    s = s.replace("ё", "е").replace("’", "'")
    s = re.sub(r"[^\w' ]+", " ", s)
    return " ".join(s.split())


def main(root):
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    proc = WhisperProcessor.from_pretrained(MODEL)
    model = WhisperForConditionalGeneration.from_pretrained(MODEL, dtype=dtype).to(dev).eval()
    path = f"{root}/results.csv"
    rows = list(csv.DictReader(open(path)))
    fields = list(rows[0].keys()) + [k for k in ("asr", "cer") if k not in rows[0]]

    def save():
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    t0 = time.time()
    for i, r in enumerate(rows):
        if r["name"] == "_reference" or r.get("asr"):
            continue  # уже распознано в прошлый запуск
        y, _ = librosa.load(f"{root}/{r['file']}", sr=16000)
        feats = proc(y, sampling_rate=16000, return_tensors="pt").input_features.to(dev, dtype)
        with torch.inference_mode():
            ids = model.generate(feats, language=LANG[r["lang"]], task="transcribe")
        r["asr"] = proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
        ref = norm(r["text"].replace(" | ", " "))
        r["cer"] = round(jiwer.cer(ref, norm(r["asr"])), 3) if ref else ""
        print(f"{i + 1}/{len(rows)} {time.time() - t0:.0f}s [{r['section']}] {r['name']}: {r['asr']!r} CER {r['cer']}", flush=True)
        if i % 20 == 0:
            save()  # прерванный запуск продолжится с этого места
    save()


if __name__ == "__main__":
    main(sys.argv[1])
