#!/usr/bin/env python3
"""Сводка по моделям: out/summary.md (скорость, память, ошибки, CER по разделам и вариантам ввода).
  python3 tts_eval/report.py out
"""
import csv
import glob
import json
import os
import statistics as st
import sys
from collections import defaultdict


def mean(xs):
    xs = [float(x) for x in xs if x not in ("", None)]
    return round(st.mean(xs), 3) if xs else ""


def main(root):
    md = ["# Локальные TTS: сводка прогона\n",
          "CER — Whisper large-v3-turbo к обычному тексту (разборчивость; ударение и долготу проверяет экспертиза).\n",
          "| модель | загрузка, с | RTF (медиана) | RAM, ГБ | GPU, ГБ | записей | ошибок | CER it | CER ru | CER he |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for d in sorted(glob.glob(f"{root}/*/")):
        m = os.path.basename(d.rstrip("/"))
        src = f"{d}asr.csv" if os.path.exists(f"{d}asr.csv") else f"{d}meta.csv"
        if not os.path.exists(src):
            continue
        rows = list(csv.DictReader(open(src)))
        allrows = list(csv.DictReader(open(f"{d}meta.csv")))
        run = json.load(open(f"{d}run.json")) if os.path.exists(f"{d}run.json") else {}
        rtf = [float(r["rtf"]) for r in allrows if r["rtf"]]
        cer = lambda lang: mean(r.get("cer") for r in rows if r["lang"] == lang)
        md.append(f"| {m} | {run.get('load_s', '')} | {round(st.median(rtf), 2) if rtf else ''} | {run.get('peak_rss_gb', '')} | "
                  f"{run.get('peak_gpu_gb', '')} | {len(allrows)} | {sum(1 for r in allrows if r['error'])} | "
                  f"{cer('it')} | {cer('ru')} | {cer('he')} |")
        by = defaultdict(list)
        for r in rows:
            by[(r["section"], r["variant"])].append(r.get("cer"))
        detail.append(f"\n## {m}\n\n| раздел | вариант | n | CER |\n|---|---|---|---|")
        detail += [f"| {s} | {v} | {len(x)} | {mean(x)} |" for (s, v), x in sorted(by.items())]
        errs = [r for r in allrows if r["error"]]
        if errs:
            detail.append(f"\nОшибки ({len(errs)}), первая: `{errs[0]['id']} {errs[0]['variant']}: {errs[0]['error'][:200]}`")
    open(f"{root}/summary.md", "w").write("\n".join(md + detail) + "\n")
    print("\n".join(md + detail))


if __name__ == "__main__":
    main(sys.argv[1])
