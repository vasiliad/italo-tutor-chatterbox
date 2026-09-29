#!/usr/bin/env python3
"""Озвучить testset.json одной моделью: out/<модель>/<id>__<вариант>.wav + meta.csv.

  python3 tts_eval/run_model.py kokoro [--out out] [--limit N]

Модель — модуль tts_eval/models/<имя>.py с функциями:
  load(device) -> объект; variants(item) -> [вариант, ...] (какие входы модель умеет);
  synth(obj, item, variant) -> (np.float32 массив, sample_rate) или None.
Каждая модель запускается в своём venv (зависимости разные), общий только этот файл.
Повторный запуск дописывает недостающие WAV (продолжение после обрыва).
"""
import argparse
import csv
import importlib
import json
import os
import resource
import sys
import time
import traceback

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def peak_gpu_gb():
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / 2**30, 2)
        if torch.backends.mps.is_available():
            return round(torch.mps.driver_allocated_memory() / 2**30, 2)
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--sections", default="", help="только эти разделы через запятую (для замера на Mac)")
    a = ap.parse_args()
    mod = importlib.import_module(f"models.{a.model}")
    device = a.device or ("cpu" if os.environ.get("FORCE_CPU") else None)
    if not device:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        except ImportError:
            device = "cpu"
    items = json.load(open(os.path.join(HERE, "testset.json")))
    if a.sections:
        items = [x for x in items if x["section"] in a.sections.split(",")]
    if a.limit:
        items = items[:a.limit]
    out = os.path.join(a.out, a.model)
    os.makedirs(out, exist_ok=True)
    meta_path = os.path.join(out, "meta.csv")
    done = set()
    if os.path.exists(meta_path):
        done = {(r["id"], r["variant"]) for r in csv.DictReader(open(meta_path))}
    t = time.time()
    obj = mod.load(device)
    load_s = time.time() - t
    print(f"[{a.model}] загрузка {load_s:.1f} с на {device}", flush=True)
    new = not os.path.exists(meta_path)
    f = open(meta_path, "a", newline="")
    w = csv.DictWriter(f, ["model", "id", "section", "lang", "variant", "text", "expected", "wav", "audio_s",
                           "gen_s", "rtf", "error"])
    if new:
        w.writeheader()
    n = 0
    for it in items:
        for v in mod.variants(it):
            if (it["id"], v) in done:
                continue
            row = dict(model=a.model, id=it["id"], section=it["section"], lang=it["lang"], variant=v,
                       text=it["inputs"].get(v, it["inputs"].get("plain")), expected=it.get("expected", ""),
                       wav="", audio_s="", gen_s="", rtf="", error="")
            try:
                t = time.time()
                res = mod.synth(obj, it, v)
                dt = time.time() - t
                if res is None:
                    continue
                y, sr = res
                y = np.asarray(y, dtype=np.float32).squeeze()
                name = f"{it['id']}__{v}.wav"
                sf.write(os.path.join(out, name), y, sr, subtype="PCM_16")
                dur = len(y) / sr
                row.update(wav=name, audio_s=round(dur, 2), gen_s=round(dt, 2), rtf=round(dt / max(dur, 0.01), 3))
            except Exception as e:
                row["error"] = f"{type(e).__name__}: {e}"[:300]
                traceback.print_exc(limit=2)
            w.writerow(row)
            f.flush()
            n += 1
            print(f"[{a.model}] {it['id']} {v}: {row['audio_s']} с за {row['gen_s']} с {row['error']}", flush=True)
    f.close()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**30 if sys.platform == "darwin" else 2**20)
    json.dump(dict(model=a.model, device=device, load_s=round(load_s, 1), peak_rss_gb=round(rss, 2),
                   peak_gpu_gb=peak_gpu_gb(), new_rows=n), open(os.path.join(out, "run.json"), "w"))
    print(f"[{a.model}] готово: {n} записей, RSS {rss:.1f} ГБ, GPU {peak_gpu_gb()} ГБ", flush=True)


if __name__ == "__main__":
    main()
