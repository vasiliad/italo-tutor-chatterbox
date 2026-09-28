#!/usr/bin/env python3
"""Замер Chatterbox Multilingual на Mac (Apple Silicon): CPU и MPS (видеочип).

Для офлайн-учителя: сколько секунд синтеза на секунду речи (RTF) и сколько памяти.
Запуск на Mac (Python 3.11, ~6 ГБ места под веса и пакеты):

  python3.11 -m venv ~/cbx && source ~/cbx/bin/activate
  pip install torch torchaudio soundfile librosa
  pip install --no-deps "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54"
  pip install s3tokenizer "conformer==0.3.2" "diffusers==0.29.0" resemble-perth pyloudnorm omegaconf einops \
      transformers "setuptools<81"   # perth импортирует pkg_resources (убран в setuptools 81)
  python3 tools/mac_bench.py            # CPU и MPS; итог — mac_bench/results.md и WAV

RTF < 1 — быстрее реального времени. Для сравнения (2026-09-28): Kaggle T4 ≈ 1.2, Kaggle CPU 4 ядра ≈ 10;
Mac mini M4 Pro 24 ГБ: CPU 2.34, MPS 1.04 (mac_bench/results.md).
"""
import json
import os
import platform
import resource
import subprocess
import sys
import time

import numpy as np
import soundfile as sf
import torch

PHRASES = [
    "Ciao, mi chiamo Paolo. Come ti chiami?",
    "Vorrei un caffè e un cornetto, per favore.",
    "Mi piace la musica, ma non mi piacciono i film dell'orrore.",
    "Scusi, a che ora parte il treno per Firenze?",
    "Dico telèfonano adesso.",
]
OUT = "mac_bench"


def rss_gb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**30 if sys.platform == "darwin" else r / 2**20  # на macOS — байты


def run(device):
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t = time.time()
    m = ChatterboxMultilingualTTS.from_pretrained(device, t3_model="v3")
    load = time.time() - t
    rows = []
    for i, text in enumerate(PHRASES):
        torch.manual_seed(i)
        t = time.time()
        wav = m.generate(text, language_id="it")
        if device == "mps":
            torch.mps.synchronize()
        dt = time.time() - t
        y = wav.squeeze(0).numpy()
        dur = len(y) / m.sr
        sf.write(f"{OUT}/{device}_{i}.wav", y, m.sr, subtype="PCM_16")
        rows.append(dict(device=device, phrase=text, audio_s=round(dur, 2), gen_s=round(dt, 2),
                         rtf=round(dt / dur, 2)))
        print(f"[{device}] {dur:.1f}s речи за {dt:.1f}s, RTF {dt / dur:.2f} — {text}", flush=True)
    mps_gb = torch.mps.driver_allocated_memory() / 2**30 if device == "mps" else None
    return dict(device=device, load_s=round(load, 1), rows=rows,
                rtf_mean_excl_first=round(float(np.mean([r["rtf"] for r in rows[1:]])), 2),
                peak_rss_gb=round(rss_gb(), 1), mps_driver_gb=round(mps_gb, 1) if mps_gb else None)


def main():
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1:  # дочерний процесс: одно устройство, чтобы память мерилась честно
        print(json.dumps(run(sys.argv[1])))
        return
    chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
    ram = f"{int(mem) / 2**30:.0f} ГБ" if mem.isdigit() else "?"
    head = f"{chip or platform.processor()}, RAM {ram}, macOS {platform.mac_ver()[0] or '—'}, torch {torch.__version__}"
    print(head)
    results = []
    devices = ["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])
    for d in devices:
        p = subprocess.run([sys.executable, __file__, d], capture_output=True, text=True)
        sys.stderr.write(p.stderr[-2000:])
        line = [l for l in p.stdout.splitlines() if l.startswith("{")]
        results.append(json.loads(line[-1]) if line else dict(device=d, error=p.stderr[-500:]))
    md = [f"# Chatterbox Multilingual v3 на Mac\n\n{head}\n",
          "| устройство | загрузка, с | RTF (без первой фразы) | пик RAM процесса, ГБ | память MPS, ГБ |",
          "|---|---|---|---|---|"]
    for r in results:
        if "error" in r:
            md.append(f"| {r['device']} | ошибка | | | |")
            continue
        md.append(f"| {r['device']} | {r['load_s']} | {r['rtf_mean_excl_first']} | {r['peak_rss_gb']} | {r['mps_driver_gb'] or '—'} |")
    open(f"{OUT}/results.md", "w").write("\n".join(md) + "\n")
    json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
