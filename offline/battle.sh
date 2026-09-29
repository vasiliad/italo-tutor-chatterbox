#!/bin/bash
# «Бой»: один и тот же урок (сценарий A1) для всех сочетаний мозг × голос, без интернета; потом судит Паоло.
#   bash offline/battle.sh [сценарий]      → offline/runs/*/ и offline/battle.md
set -u
cd "$(dirname "$0")/.."
S=${1:-offline/scenario_a1.json}
P="$HOME/offline_env/bin/python"
export HF_HUB_OFFLINE=1 IT_STRESS=${IT_STRESS:-$HOME/italo-tutor/assets/lexicon/it_stress.tsv.gz}
for b in qwen35-9b gemma4-e4b gemma4-12b; do
  for v in kokoro-piper qwen3tts; do
    echo "=== $b × $v"
    "$P" offline/lesson.py --brain $b --voice $v --scenario "$S" --no-play 2>&1 | grep -v -i warn | tail -40
  done
done
unset HF_HUB_OFFLINE
"$P" offline/judge.py --per-min 20      # Паоло (gemini-3.8-live) слушает ответы учителя — нужен интернет
