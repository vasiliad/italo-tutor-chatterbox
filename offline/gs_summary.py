#!/usr/bin/env python3
"""Сводка боёв с ученицей-Gemini: runs/*gstudent*/log.jsonl + judge.json → offline/gstudent.md"""
import glob
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
rows = ["# Бой с ученицей-Gemini (живой урок без сценария)\n",
        "Ученица — Gemini (A1, ошибки нарочно, иногда по-русски, голос Gemini 3.8 live с русским акцентом). "
        "Судья — Паоло (Gemini 3.8 live, вслепую). «Заметил ошибку» — из реплик, где ученица ошиблась нарочно.\n",
        "| прогон | реплик | оценка реплик | урок целиком | заметил ошибку | до первого звука, с (медиана / макс) | уши, с |",
        "|---|---|---|---|---|---|---|"]
notes = []
for d in sorted(glob.glob(os.path.join(HERE, "runs", "*gstudent*"))):
    lp, jp = os.path.join(d, "log.jsonl"), os.path.join(d, "judge.json")
    if not os.path.exists(jp):
        continue
    turns = [r for r in map(json.loads, open(lp)) if r.get("event") == "turn"]
    j = json.load(open(jp))
    sc = [t["score"] for t in j["turns"] if isinstance(t.get("score"), (int, float))]
    by_n = {t["n"]: t for t in j["turns"]}
    err = [t for t in turns if t.get("intended_error")]
    caught = sum(1 for t in err if by_n.get(t["n"], {}).get("caught_error") is True)
    lat = [t["reply_latency_s"] for t in turns if t.get("reply_latency_s") is not None]
    name = os.path.basename(d)
    rows.append(f"| {name} | {len(turns)} | {round(st.mean(sc), 2) if sc else '—'} | {j['lesson'].get('score', '—')} | "
                f"{caught}/{len(err)} | {round(st.median(lat), 1) if lat else '—'} / {max(lat) if lat else '—'} | "
                f"{round(st.median(t['asr_s'] for t in turns), 2) if turns else '—'} |")
    L = j["lesson"]
    notes.append(f"\n## {name}\n- **хорошо:** {L.get('good', '')}\n- **плохо:** {L.get('bad', '')}\n"
                 f"- **исправить в инструкции:** {L.get('fix', L.get('comment', ''))}")
open(os.path.join(HERE, "gstudent.md"), "w").write("\n".join(rows + notes) + "\n")
print("\n".join(rows + notes))
