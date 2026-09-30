#!/usr/bin/env python3
"""Досудить готовый урок с ученицей-Gemini (если судья оборвался): runs/<прогон>/judge.json.
  python offline/judge_run.py offline/runs/<прогон>"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_student import judge_lesson, judge_turn

run = sys.argv[1]
turns = [t for t in map(json.loads, open(os.path.join(run, "log.jsonl"))) if t.get("event") == "turn"]
scores = []
for t in turns:
    try:
        j = judge_turn(t["student_said"] or t["heard"], t.get("intended_error"),
                       open(os.path.join(run, "wav", f"{t['n']:02d}_teacher.wav"), "rb").read())
    except Exception as e:
        j = {"score": None, "comment": f"[судья недоступен: {e}]"}
    j["n"] = t["n"]
    scores.append(j)
    print(f"#{t['n']}: {j.get('score')} {j.get('comment', '')[:100]}", flush=True)
try:
    lesson = judge_lesson(turns)
except Exception as e:
    lesson = {"score": None, "comment": f"[судья недоступен: {e}]"}
print("урок:", json.dumps(lesson, ensure_ascii=False)[:300])
json.dump(dict(turns=scores, lesson=lesson), open(os.path.join(run, "judge.json"), "w"), ensure_ascii=False, indent=1)
