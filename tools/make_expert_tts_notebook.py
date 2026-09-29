#!/usr/bin/env python3
"""Собирает expert_tts.ipynb — слепая экспертиза записей tts_eval на gemini-3.8-live (CPU, интернет).
Вход: вывод ноутбука italo-tutor-local-tts-eval (Input) и приватный Dataset key-google с ключами.
  python3 tools/make_expert_tts_notebook.py && python3 tools/kaggle_api.py push --task expert_tts
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CELLS = [
    ("md", "# Экспертиза на слух: локальные TTS (tts_eval) — Паоло (it, ru) и Хава (he), gemini-3.8-live\n\n"
           "Слепой выбор: какой слог ударный, какое слово омографа, одна или две согласные. "
           "Темп ≤ 20 запросов в минуту на ключ, ключи из разных проектов — по потоку на ключ."),
    ("code", "!pip install -q websockets soundfile\n"
             "!rm -rf /kaggle/working/task && git clone -q --depth 1 https://github.com/vasiliad/italo-tutor-chatterbox /kaggle/working/task"),
    ("code", '''import os, glob, re, shutil, subprocess, zipfile
keys = []
for f in glob.glob("/kaggle/input/**/*.txt", recursive=True):   # приватный Dataset key-google
    found = [k for k in re.findall(r"[A-Za-z0-9_.\\-]{30,}", open(f).read()) if k not in keys]
    print(os.path.basename(f), "— ключей:", len(found), "длины:", [len(k) for k in found])
    keys += found
assert keys, "Нет ключей: подключите Dataset key-google"
os.makedirs(os.path.expanduser("~/key"), exist_ok=True)
open(os.path.expanduser("~/key/key"), "w").write("\\n".join(keys))
src = glob.glob("/kaggle/input/**/out/summary.md", recursive=True)
assert src, "Нет вывода italo-tutor-local-tts-eval"
base = os.path.dirname(os.path.dirname(src[0]))
OUT = "/kaggle/working/out"
shutil.rmtree(OUT, ignore_errors=True); shutil.copytree(f"{base}/out", OUT)
for z in glob.glob(f"{base}/wav_*.zip"):
    m = os.path.basename(z)[4:-4]
    for info in zipfile.ZipFile(z).infolist():  # zip без флага UTF-8: кириллица в именах пришла как cp437
        name = info.filename if info.flag_bits & 0x800 else info.filename.encode("cp437").decode("utf-8")
        open(f"{OUT}/{m}/{name}", "wb").write(zipfile.ZipFile(z).read(info))
print({m: len(glob.glob(f"{OUT}/{m}/*.wav")) for m in os.listdir(OUT) if os.path.isdir(f"{OUT}/{m}")})'''),
    ("code", "# проверка связи: 3 задания\n!cd /kaggle/working/task && python3 tts_eval/expert_tts.py --out /kaggle/working/out --limit 3 --syllable"),
    ("code", "# слепой режим: слово не называем, Паоло говорит номер ударного слога\n"
             "!cd /kaggle/working/task && python3 tts_eval/expert_tts.py --out /kaggle/working/out --per-min 20 --syllable"),
    ("code", '''res = "/kaggle/working/expert_out"
os.makedirs(res, exist_ok=True)
for f in glob.glob(f"{OUT}/expert_tts.*"):
    shutil.copy(f, res)
print(open(f"{res}/expert_tts.md").read())
shutil.rmtree(OUT); shutil.rmtree("/kaggle/working/task", ignore_errors=True)
os.remove(os.path.expanduser("~/key/key"))'''),
]


def cell(kind, src):
    c = {"cell_type": "markdown" if kind == "md" else "code", "metadata": {}, "source": src.splitlines(True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


nb = {"cells": [cell(k, s) for k, s in CELLS],
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                   "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
(ROOT / "expert_tts.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1))
print("expert_tts.ipynb:", len(nb["cells"]), "ячеек")
