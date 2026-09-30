#!/bin/bash
# Один раз, с интернетом: среда и модели для офлайн-урока (≈ 20 ГБ). Дальше всё работает без сети.
#   bash offline/setup.sh            (Python 3.11+, Apple Silicon)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3.11}
M=${OFFLINE_MODELS:-$HOME/offline_models}
mkdir -p "$M"
[ -d "$HOME/offline_env" ] || $PY -m venv "$HOME/offline_env"
E="$HOME/offline_env/bin"
"$E/pip" install -q -U mlx-lm mlx-audio sherpa-onnx sounddevice soundfile numpy huggingface_hub websockets
# мозги и голос Qwen3-TTS (MLX)
# и уши на выбор (mlx-audio STT) для offline/asr_bench.py
for r in mlx-community/Qwen3.5-9B-4bit lmstudio-community/gemma-4-E4B-it-MLX-4bit mlx-community/gemma-4-12B-it-4bit \
         mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit \
         mlx-community/nemotron-3.5-asr-streaming-0.6b mlx-community/Qwen3-ASR-0.6B-8bit \
         mlx-community/Qwen3-ASR-1.7B-8bit mlx-community/whisper-large-v3-turbo; do
  "$E/python" -c "from huggingface_hub import snapshot_download as s; s('$r')"
done
# токенизатор Whisper (в mlx-community-версии его нет) — только конфиги и словарь, без весов
"$E/python" -c "from huggingface_hub import snapshot_download as s; s('openai/whisper-large-v3-turbo', allow_patterns=['*.json','*.txt'])"
# sherpa-onnx: Kokoro, Piper ru (Паоло — dmitri, ученица — irina), Parakeet v3
REL=https://github.com/k2-fsa/sherpa-onnx/releases/download
for a in tts-models/kokoro-int8-multi-lang-v1_0 tts-models/vits-piper-ru_RU-dmitri-medium \
         tts-models/vits-piper-ru_RU-irina-medium asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8; do
  d="$M/$(basename $a)"
  [ -d "$d" ] || curl -sSL "$REL/$a.tar.bz2" | tar xj -C "$M"
done
# русское ударение знаком U+0301 для Piper (правила upstream espeak-ng, см. italo-tutor tools/offline/); нужен cmake
command -v cmake >/dev/null || brew install cmake
T=${ITALO_TUTOR:-$HOME/italo-tutor}
for v in dmitri irina; do
  bash "$T/tools/offline/espeak_ru_stress.sh" "$M/vits-piper-ru_RU-$v-medium/espeak-ng-data" "$M/.espeak_build"
done
echo "готово: $M"
