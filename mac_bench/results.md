# Chatterbox Multilingual v3 на Mac

Apple M4 Pro, RAM 24 ГБ, macOS 26.6.2, torch 2.14.0

| устройство | загрузка, с | RTF (без первой фразы) | пик RAM процесса, ГБ | память MPS, ГБ |
|---|---|---|---|---|
| cpu | 7.2 | 2.34 | 6.5 | — |
| mps | 8.5 | 1.04 | 4.9 | 3.6 |

Замер 2026-09-28, Mac mini. Установка по шапке `tools/mac_bench.py`, но её не хватило — пришлось доставить:
- `transformers==5.2.0` (иначе `No module named 'transformers'`);
- `setuptools<81` (perth импортирует `pkg_resources`, без него `PerthImplicitWatermarker` = None → `TypeError`).

Версии: torch 2.14.0, torchaudio 2.11.0 (chatterbox просит 2.6.0 — не мешает). MPS отработал без ошибок.
Первая фраза (прогрев): CPU RTF 3.95, MPS 3.7.
