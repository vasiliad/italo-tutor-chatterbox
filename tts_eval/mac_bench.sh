#!/bin/bash
# Замер локальных TTS на Mac (Apple Silicon): скорость (RTF) и память, устройство MPS (видеочип) и CPU.
# Те же адаптеры и фразы, что на Kaggle (tts_eval/), только разделы it_a1, it_context, ru — ≈25 фраз на модель.
#   bash tts_eval/mac_bench.sh            # все модели;  bash tts_eval/mac_bench.sh kokoro piper — выборочно
# Итог: mac_bench_tts/<прогон>/meta.csv + run.json и сводка mac_bench_tts/results.md. Место: ≈25 ГБ (веса + venv).
set -u
cd "$(dirname "$0")/.."
PY=${PY:-python3.11}
OUT=mac_bench_tts
ENVS=${ENVS:-$HOME/tts_envs}
SECTIONS=it_a1,it_context,ru
mkdir -p "$OUT" "$ENVS"
command -v espeak-ng >/dev/null || brew install espeak-ng

run() {  # имя venv | pip-пакеты | адаптер | имя прогона | переменные окружения...
  local venv=$1 pip=$2 model=$3 name=$4; shift 4
  [ -d "$ENVS/$venv" ] || { $PY -m venv "$ENVS/$venv" && "$ENVS/$venv/bin/pip" install -q torch torchaudio soundfile numpy $pip; }
  echo "=== $name ($(date +%H:%M))"
  rm -rf "$OUT/$model"
  env "$@" /usr/bin/time -l "$ENVS/$venv/bin/python" tts_eval/run_model.py "$model" --out "$OUT" --sections $SECTIONS \
      2> >(grep -E "maximum resident|Error|error" >&2)
  [ -d "$OUT/$model" ] && rm -rf "$OUT/$name" && mv "$OUT/$model" "$OUT/$name"
}

want() { [ $# -eq 0 ] || [[ " $ARGS " == *" $1 "* ]]; }
ARGS="$*"
if want piper; then
  [ -d "$ENVS/piper" ] || { $PY -m venv "$ENVS/piper" && "$ENVS/piper/bin/pip" install -q piper-tts soundfile numpy; }
  [ -f "$ENVS/piper_voices/it_IT-paola-medium.onnx" ] || \
    "$ENVS/piper/bin/python" -m piper.download_voices --download-dir "$ENVS/piper_voices" it_IT-paola-medium ru_RU-irina-medium
  run piper "" piper piper PIPER_VOICES="$ENVS/piper_voices"
fi
want kokoro && { run kokoro "kokoro>=0.9.4" kokoro kokoro_mps PYTORCH_ENABLE_MPS_FALLBACK=1;
                 run kokoro "kokoro>=0.9.4" kokoro kokoro_cpu FORCE_CPU=1; }
want qwen3 && { run qwen3 "qwen-tts" qwen3 qwen3_17b_mps QWEN_MODE=voice QWEN_SIZE=1.7B;
                run qwen3 "qwen-tts" qwen3 qwen3_06b_mps QWEN_MODE=voice QWEN_SIZE=0.6B; }
want moss && { M='transformers==5.0.0 accelerate torchcodec einops librosa'
               run moss "$M" moss moss_v15_mps MOSS_REPO=OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5;
               run moss "$M" moss moss_v10_mps MOSS_REPO=OpenMOSS-Team/MOSS-TTS-Local-Transformer; }

# сводка
python3 - "$OUT" <<'PY'
import csv, glob, json, os, statistics as st, sys, platform, subprocess
out = sys.argv[1]
chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
mem = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip()
md = [f"# Локальные TTS на Mac\n\n{chip}, RAM {int(mem) / 2**30:.0f} ГБ, macOS {platform.mac_ver()[0]}\n",
      "| прогон | устройство | загрузка, с | RTF медиана | RTF макс | пик RAM, ГБ | MPS, ГБ | фраз | ошибок |", "|---|---|---|---|---|---|---|---|---|"]
for d in sorted(glob.glob(f"{out}/*/")):
    if not os.path.exists(d + "run.json"):
        continue
    r = json.load(open(d + "run.json")); rows = list(csv.DictReader(open(d + "meta.csv")))
    rtf = [float(x["rtf"]) for x in rows if x["rtf"]][1:] or [0]
    md.append(f"| {os.path.basename(d.rstrip('/'))} | {r['device']} | {r['load_s']} | {st.median(rtf):.2f} | {max(rtf):.2f} | "
              f"{r['peak_rss_gb']} | {r.get('peak_gpu_gb') or '—'} | {len(rows)} | {sum(1 for x in rows if x['error'])} |")
open(f"{out}/results.md", "w").write("\n".join(md) + "\n"); print("\n".join(md))
PY
