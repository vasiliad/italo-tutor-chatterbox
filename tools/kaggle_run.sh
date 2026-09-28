#!/usr/bin/env bash
# Запуск chatterbox_eval.ipynb на Kaggle через API и скачивание результата.
# Нужны переменные окружения KAGGLE_USERNAME и KAGGLE_KEY (Kaggle → Settings → API → Create New Token)
# и сетевой доступ к kaggle.com. Использование:
#   tools/kaggle_run.sh push     — отправить ноутбук и запустить (GPU, интернет включены)
#   tools/kaggle_run.sh status   — статус выполнения
#   tools/kaggle_run.sh output   — скачать результат в ./kaggle_output/
set -euo pipefail
cd "$(dirname "$0")/.."
: "${KAGGLE_USERNAME:?нет KAGGLE_USERNAME}" "${KAGGLE_KEY:?нет KAGGLE_KEY}"
command -v kaggle >/dev/null || pip install -q kaggle
SLUG="italo-tutor-chatterbox-eval"
KERNEL="$KAGGLE_USERNAME/$SLUG"
ACCEL="${KAGGLE_ACCELERATOR:-NvidiaTeslaT4}"   # можно переопределить, напр. другой ускоритель
case "${1:-}" in
  push)
    mkdir -p kaggle_push
    cp chatterbox_eval.ipynb kaggle_push/
    cat > kaggle_push/kernel-metadata.json <<JSON
{
  "id": "$KERNEL",
  "title": "$SLUG",
  "code_file": "chatterbox_eval.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": true,
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": []
}
JSON
    kaggle kernels push -p kaggle_push --accelerator "$ACCEL" 2>/dev/null || kaggle kernels push -p kaggle_push
    ;;
  status) kaggle kernels status "$KERNEL" ;;
  output) mkdir -p kaggle_output && kaggle kernels output "$KERNEL" -p kaggle_output ;;
  *) echo "usage: $0 push|status|output"; exit 1 ;;
esac
