#!/usr/bin/env python3
"""Выбор ушей для урока: все --ears на одних и тех же фразах ученицы (offline/asr_testset.json).
Фразы говорит «ученица» (Kokoro it / Piper ru, женские голоса; смешанные — каждым голосом свой кусок).
Главное — дошли ли до учителя буквально ошибки ученицы и имена (keep): уши, которые «исправляют»
quatro → quattro или пишут числа цифрами, учителю не годятся.
  python offline/asr_bench.py [--ears parakeet nemotron ...] [--wav-dir DIR]   → offline/asr_bench.md
--wav-dir: свои записи вместо синтеза (NN.wav по порядку фраз) — например, голос владельца.
"""
import argparse
import json
import os
import re
import statistics as st
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lesson as L  # noqa: E402


def words(s):
    return re.sub(r"[^\w]+", " ", s.lower().replace("’", "'")).split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ears", nargs="+", default=list(L.EARS))
    ap.add_argument("--wav-dir")
    a = ap.parse_args()
    items = json.load(open(os.path.join(HERE, "asr_testset.json")))["items"]
    wav_dir = a.wav_dir or os.path.join(HERE, "runs", "asr_wav")
    os.makedirs(wav_dir, exist_ok=True)
    if not a.wav_dir:
        voice = L.SherpaVoices(male=False)
        for i, it in enumerate(items):
            sf.write(os.path.join(wav_dir, f"{i:02d}.wav"), L.resample(L.speak(voice, it["text"]), 24000, 16000), 16000)
    audio = [sf.read(os.path.join(wav_dir, f"{i:02d}.wav"), dtype="float32")[0] for i in range(len(items))]
    res = {}
    for name in a.ears:
        t = time.time()
        try:
            ears = L.Ears(name)
        except Exception as e:
            print(f"{name}: не загрузилось: {e}", flush=True)
            continue
        load_s = round(time.time() - t, 1)
        ears.hear(audio[0])  # прогрев
        rows = []
        for it, y in zip(items, audio):
            heard, dt = ears.hear(y)
            got = words(heard)
            lost = [k for k in it["keep"] if words(k)[0] not in got]
            rows.append(dict(text=it["text"], heard=heard, s=dt, exact=words(it["text"]) == got, lost=lost))
            print(f"{name}: {it['text']!r} → {heard!r}{'  ПОТЕРЯНО: ' + ', '.join(lost) if lost else ''}", flush=True)
        res[name] = dict(load_s=load_s, rows=rows)
        del ears
    json.dump(res, open(os.path.join(HERE, "runs", "asr_bench.json"), "w"), ensure_ascii=False, indent=1)

    md = ["# Выбор ушей: фразы ученицы (offline/asr_testset.json)\n",
          f"Источник звука: {'записи ' + a.wav_dir if a.wav_dir else 'синтез Kokoro it / Piper ru (женские голоса)'}. "
          "«Дошло буквально» — ошибки ученицы, имена и числа словами дошли до учителя как сказаны.\n",
          "| уши | дошло буквально (keep) | фраз без потерь | точно слово в слово | время на фразу, с (медиана) | загрузка, с |",
          "|---|---|---|---|---|---|"]
    nkeep = sum(len(it["keep"]) for it in items)
    for name, r in res.items():
        lost = sum(len(x["lost"]) for x in r["rows"])
        md.append(f"| {name} | {nkeep - lost}/{nkeep} | {sum(not x['lost'] for x in r['rows'])}/{len(items)} | "
                  f"{sum(x['exact'] for x in r['rows'])}/{len(items)} | {st.median(x['s'] for x in r['rows'])} | {r['load_s']} |")
    md.append("\n## Потери по фразам\n")
    for i, it in enumerate(items):
        bad = [f"{n}: «{r['rows'][i]['heard']}»" for n, r in res.items() if r["rows"][i]["lost"]]
        if bad:
            md.append(f"- **{it['text']}** — " + "; ".join(bad))
    open(os.path.join(HERE, "asr_bench.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
