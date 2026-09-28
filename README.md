# italo-tutor-chatterbox

Проверка [Chatterbox Multilingual TTS](https://github.com/resemble-ai/chatterbox) (Resemble AI) для
[italo-tutor](https://github.com/vasiliad/italo-tutor) на Kaggle. Отчёт о модели лежит в основном репозитории:
`docs/research/chatterbox_tts.md`.

## Запуск на Kaggle

1. kaggle.com → **Create → New Notebook → File → Import Notebook → GitHub**, вставить
   `https://github.com/vasiliad/italo-tutor-chatterbox/blob/main/chatterbox_eval.ipynb`.
2. **Settings**: **Internet = On**, ускоритель любой. Ноутбук сам выберет CUDA, если torch 2.6 знает
   эту видеокарту, иначе все ядра CPU. На CPU по умолчанию `QUICK = True` (~60 записей вместо ~200).
3. **Run All**. Записи Паоло для клона голоса ноутбук сам клонирует отсюда (`refs/`).
4. **Output** → скачать `chatterbox_eval.zip`, распаковать, открыть `report.html`.

## Что проверяется

Знаки ударения в токенайзере · итальянский A1 (v3 и v2) · ударение без знака / с грависом / с острым знаком ·
итальянские омографы в контексте (ancora, principi, capitano, subito) и неоднозначная фраза ·
иврит: базовые фразы, выбор слова по контексту без огласовок / с огласовками Dicta / вручную, неоднозначная фраза,
знак ударения ole ·
двойные согласные · русский с ударениями и 8 повторов (issue #360) · смешанная фраза ru+it ·
клон голоса Паоло · медленное чтение · скорость GPU/CPU · размер весов · CER по Whisper large-v3-turbo.

## Файлы

- `chatterbox_eval.ipynb` — задача для Kaggle (собирается скриптом `tools/make_notebook.py`)
- `refs/` — образцы голоса Паоло (Gemini, голос Algenib), 24 кГц, русская речь
