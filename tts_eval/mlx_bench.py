"""RTF на MLX (mlx-audio) для сравнения с MPS: 5 фраз it_a1, первая — прогрев (№13 п.4).
  ~/tts_envs/mlx/bin/python tts_eval/mlx_bench.py <repo> [voice] [lang_code]"""
import json, os, statistics as st, sys, time
import numpy as np, soundfile as sf
from mlx_audio.tts.utils import load_model

repo = sys.argv[1]
voice = sys.argv[2] if len(sys.argv) > 2 else None
lang = sys.argv[3] if len(sys.argv) > 3 else None
here = os.path.dirname(os.path.abspath(__file__))
items = [t for t in json.load(open(os.path.join(here, "testset.json"))) if t["section"] == "it_a1"][:6]
t0 = time.time(); model = load_model(repo); load = time.time() - t0
out = os.path.join(here, "..", "mac_bench_tts", "mlx_" + repo.split("/")[-1]); os.makedirs(out, exist_ok=True)
rows = []
for i, t in enumerate(items):
    kw = {"text": t["inputs"]["plain"]}
    if voice: kw["voice"] = voice
    if lang: kw["lang_code"] = lang
    t1 = time.time()
    chunks, sr = [], 24000
    for r in model.generate(**kw):
        chunks.append(np.array(r.audio)); sr = getattr(r, "sample_rate", sr)
    dt = time.time() - t1
    y = np.concatenate(chunks) if chunks else np.zeros(1)
    dur = len(y) / sr
    sf.write(os.path.join(out, f"{t['id']}.wav"), y, sr)
    rows.append({"id": t["id"], "audio_s": round(dur, 2), "gen_s": round(dt, 2), "rtf": round(dt / max(dur, 1e-3), 3)})
    print(rows[-1], flush=True)
rtf = [r["rtf"] for r in rows[1:]]
import resource
res = {"repo": repo, "load_s": round(load, 1), "rtf_median": round(st.median(rtf), 3), "rtf_max": max(rtf),
       "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30, 2), "rows": rows}
json.dump(res, open(os.path.join(out, "run.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "rows"}))
