#!/usr/bin/env python3
"""Паоло (gemini-3.8-live) слушает реплики офлайн-учителя из offline/runs/* и ставит оценки.
Что за мозг и голос — не знает. На каждую реплику: что сказала ученица (текст) + звук учителя.
Итог: offline/battle.md — по сочетаниям: оценки, задержка до первого звука, скорость мозга, память.
  python offline/judge.py [--per-min 20] [--keys ~/key/key]
"""
import argparse
import asyncio
import csv
import glob
import json
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "expert"))
from expert_listen import Pacer, load_16k, parse, run_one  # noqa: E402
from paolo import load_keys  # noqa: E402

Q = ("Это слепая проверка офлайн-учителя итальянского для нашей школы (без интернета). Ученица (A1, русская) сказала: "
     "«{said}». Сейчас ты услышишь ответ учителя. Оцени его как коллега: правильность итальянского, произношение и "
     "ударения, естественность голоса, и хорош ли это ответ учителя (по делу, коротко, исправил ли ошибку). "
     "Ответь строго так: «Оценка: <число от 1 до 5>», потом одной-двумя фразами — главные плюсы и минусы.")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-min", type=float, default=20)
    ap.add_argument("--keys", default="~/key/key")
    ap.add_argument("--model", default="models/gemini-3.8-live")
    a = ap.parse_args()
    keys = load_keys(a.keys)
    runs = sorted(glob.glob(os.path.join(HERE, "runs", "*", "log.jsonl")))
    out_csv = os.path.join(HERE, "runs", "judge.csv")
    done = {}
    if os.path.exists(out_csv):
        done = {(r["run"], r["n"]): r for r in csv.DictReader(open(out_csv)) if not r["transcript"].startswith("[")}
    jobs = []
    for lp in runs:
        run = os.path.basename(os.path.dirname(lp))
        for rec in map(json.loads, open(lp)):
            if rec.get("event") == "turn" and (run, str(rec["n"])) not in done:
                jobs.append((run, rec))
    print(f"реплик на оценку: {len(jobs)}, ключей: {len(keys)}", flush=True)
    queue = asyncio.Queue()
    for j in jobs:
        queue.put_nowait(j)
    results = dict(done)

    async def worker(i):
        pacer = Pacer(a.per_min)
        while not queue.empty():
            run, rec = queue.get_nowait()
            audio = load_16k(os.path.join(HERE, "runs", run, "wav", f"{rec['n']:02d}_teacher.wav"))
            task = dict(expert="paolo", question=Q.format(said=rec.get("student_said") or rec["heard"]))
            ans = await run_one(task, audio, [keys[i]], [pacer], 0, 120, False, a.model)
            score = parse("rate", ans)
            results[(run, str(rec["n"]))] = dict(run=run, n=rec["n"], score=score if score else "", transcript=ans)
            print(f"{run} #{rec['n']}: {score} {ans[:100]!r}", flush=True)

    await asyncio.gather(*(worker(i) for i in range(len(keys))))
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, ["run", "n", "score", "transcript"])
        w.writeheader()
        w.writerows(results.values())

    md = ["# Офлайн-урок «в бою»: сводка\n",
          "Оценка — Паоло (gemini-3.8-live) вслепую, 1–5. Задержка — от конца реплики ученицы до первого звука ответа "
          "(распознавание + мозг целиком + первый кусок голоса).\n",
          "| мозг | голос | оценка Паоло | задержка, с (медиана / макс) | мозг, ток/с | ошибки распознавания | пик RAM, ГБ |",
          "|---|---|---|---|---|---|---|"]
    for lp in runs:
        run = os.path.basename(os.path.dirname(lp))
        recs = list(map(json.loads, open(lp)))
        turns = [r for r in recs if r.get("event") == "turn"]
        end = next((r for r in recs if r.get("event") == "end"), {})
        sc = [int(v["score"]) for (rr, _), v in results.items() if rr == run and str(v["score"]).isdigit()]
        lat = [t["reply_latency_s"] for t in turns]
        words = lambda s: re.sub(r"[^\w]+", " ", s.lower()).split()
        asr_bad = sum(1 for t in turns if t.get("student_said") and words(t["student_said"]) != words(t["heard"]))
        b, v = run.split("__")[:2]
        md.append(f"| {b} | {v} | {round(st.mean(sc), 2) if sc else '—'} ({len(sc)}) | "
                  f"{round(st.median(lat), 1) if lat else '—'} / {max(lat) if lat else '—'} | "
                  f"{round(st.median([t['llm_tok_s'] for t in turns]), 1) if turns else '—'} | {asr_bad}/{len(turns)} | "
                  f"{end.get('peak_rss_gb', '—')} |")
    open(os.path.join(HERE, "battle.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    asyncio.run(main())
