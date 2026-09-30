#!/bin/bash
# «Бой»: один и тот же урок (сценарий A1) для сочетаний мозг × голос, без интернета; потом судит Паоло.
#   bash offline/battle.sh                                     — все 3 мозга × 2 голоса, уши parakeet
#   BRAINS="gemma4-e4b" EARS=qwen3asr-1.7b TAG=v2 bash offline/battle.sh   — повтор для выбранного
# → offline/runs/*/ и offline/battle.md
set -u
cd "$(dirname "$0")/.."
S=${1:-offline/scenario_a1.json}
P="$HOME/offline_env/bin/python"
BRAINS=${BRAINS:-"qwen35-9b gemma4-e4b gemma4-12b"}
VOICES=${VOICES:-"kokoro-piper qwen3tts"}
EARS=${EARS:-parakeet}
TAG=${TAG:-}
export HF_HUB_OFFLINE=1 IT_STRESS=${IT_STRESS:-$HOME/italo-tutor/assets/lexicon/it_stress.tsv.gz}
for b in $BRAINS; do
  for v in $VOICES; do
    echo "=== $b × $v × $EARS"
    "$P" offline/lesson.py --brain $b --voice $v --ears $EARS ${TAG:+--tag $TAG} --scenario "$S" --no-play 2>&1 \
      | grep -v -i warn | tail -60
  done
done
unset HF_HUB_OFFLINE
"$P" offline/judge.py --per-min 20      # Паоло (gemini-3.8-live) слушает ответы учителя — нужен интернет
