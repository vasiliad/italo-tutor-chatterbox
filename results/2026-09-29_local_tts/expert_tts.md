# Экспертиза на слух (models/gemini-3.8-live)

Верно — эксперт выбрал задуманное (ударение / слово / одна-две согласные). Оценка 1–5 — фразы A1.

## Итог по моделям (ударение и омографы it: it_solo + it_stress + it_context)

| модель | вариант | верно | % | геминаты | ru | he | оценка A1 |
|---|---|---|---|---|---|---|---|
| kokoro | accent | 24/30 | 80 | 8/14 |  |  |  |
| kokoro | ipa | 24/28 | 86 | 10/12 |  |  |  |
| kokoro | ipa_len | 0/0 |  | 10/13 |  |  |  |
| kokoro | plain | 20/21 | 95 | 10/13 |  |  | 5.0 |
| magpie | accent | 22/25 | 88 | 12/14 |  |  |  |
| magpie | plain | 18/20 | 90 | 10/13 |  |  | 5.0 |
| moss_v10 | accent | 22/27 | 81 | 8/13 | 5/6 |  |  |
| moss_v10 | clone | 0/0 |  |  | 4/6 |  | 5.0 |
| moss_v10 | ipa_len_word | 0/0 |  | 5/14 |  |  |  |
| moss_v10 | ipa_word | 13/27 | 48 | 8/13 | 3/5 |  |  |
| moss_v10 | plain | 19/21 | 90 | 7/13 | 4/6 |  | 4.9 |
| moss_v15 | accent | 24/27 | 89 | 9/14 | 2/3 |  |  |
| moss_v15 | clone | 0/0 |  |  | 6/6 |  | 5.0 |
| moss_v15 | ipa_len_word | 0/0 |  | 6/13 |  |  |  |
| moss_v15 | ipa_word | 18/29 | 62 | 7/12 | 3/5 |  |  |
| moss_v15 | niqqud | 0/0 |  |  |  | 3/7 |  |
| moss_v15 | plain | 19/21 | 90 | 12/14 | 5/6 | 2/6 | 5.0 |
| piper | accent | 21/28 | 75 | 10/14 | 5/6 |  |  |
| piper | ipa | 17/24 | 71 | 9/13 | 5/6 |  |  |
| piper | ipa_len | 0/0 |  | 10/14 |  |  |  |
| piper | plain | 19/21 | 90 | 10/13 | 5/6 |  | 4.9 |
| qwen3_clone | accent | 8/8 | 100 |  | 6/6 |  |  |
| qwen3_clone | plain | 8/8 | 100 |  | 5/6 |  | 5.0 |
| qwen3_voice | accent | 24/27 | 89 | 11/13 | 6/6 |  |  |
| qwen3_voice | plain | 18/21 | 86 | 11/13 | 3/4 |  | 4.9 |

## По разделам

| модель | раздел | вариант | n | верно / с эталоном |
|---|---|---|---|---|
| kokoro | it_a1 | plain | 10 | 0/0 |
| kokoro | it_context | accent | 8 | 6/8 |
| kokoro | it_context | ipa | 8 | 7/7 |
| kokoro | it_context | plain | 8 | 7/7 |
| kokoro | it_gem | accent | 14 | 8/14 |
| kokoro | it_gem | ipa | 14 | 10/12 |
| kokoro | it_gem | ipa_len | 14 | 10/13 |
| kokoro | it_gem | plain | 14 | 10/13 |
| kokoro | it_solo | accent | 10 | 8/10 |
| kokoro | it_solo | ipa | 10 | 6/9 |
| kokoro | it_solo | plain | 10 | 2/2 |
| kokoro | it_stress | accent | 12 | 10/12 |
| kokoro | it_stress | ipa | 12 | 11/12 |
| kokoro | it_stress | plain | 12 | 11/12 |
| magpie | it_a1 | plain | 10 | 0/0 |
| magpie | it_context | accent | 8 | 7/8 |
| magpie | it_context | plain | 8 | 8/8 |
| magpie | it_gem | accent | 14 | 12/14 |
| magpie | it_gem | plain | 14 | 10/13 |
| magpie | it_solo | accent | 10 | 7/9 |
| magpie | it_solo | plain | 10 | 2/2 |
| magpie | it_stress | accent | 12 | 8/8 |
| magpie | it_stress | plain | 12 | 8/10 |
| moss_v10 | it_a1 | clone | 10 | 0/0 |
| moss_v10 | it_a1 | plain | 10 | 0/0 |
| moss_v10 | it_context | accent | 8 | 6/6 |
| moss_v10 | it_context | ipa_word | 8 | 4/6 |
| moss_v10 | it_context | plain | 8 | 8/8 |
| moss_v10 | it_gem | accent | 14 | 8/13 |
| moss_v10 | it_gem | ipa_len_word | 14 | 5/14 |
| moss_v10 | it_gem | ipa_word | 14 | 8/13 |
| moss_v10 | it_gem | plain | 14 | 7/13 |
| moss_v10 | it_solo | accent | 10 | 6/10 |
| moss_v10 | it_solo | ipa_word | 10 | 4/10 |
| moss_v10 | it_solo | plain | 10 | 2/2 |
| moss_v10 | it_stress | accent | 12 | 10/11 |
| moss_v10 | it_stress | ipa_word | 12 | 5/11 |
| moss_v10 | it_stress | plain | 12 | 9/11 |
| moss_v10 | ru | accent | 6 | 5/6 |
| moss_v10 | ru | clone | 7 | 4/6 |
| moss_v10 | ru | ipa_word | 6 | 3/5 |
| moss_v10 | ru | plain | 7 | 4/6 |
| moss_v15 | he | niqqud | 7 | 3/7 |
| moss_v15 | he | plain | 7 | 2/6 |
| moss_v15 | it_a1 | clone | 10 | 0/0 |
| moss_v15 | it_a1 | plain | 10 | 0/0 |
| moss_v15 | it_context | accent | 8 | 7/7 |
| moss_v15 | it_context | ipa_word | 8 | 7/8 |
| moss_v15 | it_context | plain | 8 | 6/7 |
| moss_v15 | it_gem | accent | 14 | 9/14 |
| moss_v15 | it_gem | ipa_len_word | 14 | 6/13 |
| moss_v15 | it_gem | ipa_word | 14 | 7/12 |
| moss_v15 | it_gem | plain | 14 | 12/14 |
| moss_v15 | it_solo | accent | 10 | 6/8 |
| moss_v15 | it_solo | ipa_word | 10 | 3/9 |
| moss_v15 | it_solo | plain | 10 | 2/2 |
| moss_v15 | it_stress | accent | 12 | 11/12 |
| moss_v15 | it_stress | ipa_word | 12 | 8/12 |
| moss_v15 | it_stress | plain | 12 | 11/12 |
| moss_v15 | ru | accent | 6 | 2/3 |
| moss_v15 | ru | clone | 7 | 6/6 |
| moss_v15 | ru | ipa_word | 6 | 3/5 |
| moss_v15 | ru | plain | 7 | 5/6 |
| piper | it_a1 | plain | 10 | 0/0 |
| piper | it_context | accent | 8 | 6/7 |
| piper | it_context | ipa | 8 | 6/7 |
| piper | it_context | plain | 8 | 7/8 |
| piper | it_gem | accent | 14 | 10/14 |
| piper | it_gem | ipa | 14 | 9/13 |
| piper | it_gem | ipa_len | 14 | 10/14 |
| piper | it_gem | plain | 14 | 10/13 |
| piper | it_solo | accent | 10 | 6/9 |
| piper | it_solo | ipa | 10 | 6/10 |
| piper | it_solo | plain | 10 | 2/2 |
| piper | it_stress | accent | 12 | 9/12 |
| piper | it_stress | ipa | 12 | 5/7 |
| piper | it_stress | plain | 12 | 10/11 |
| piper | ru | accent | 6 | 5/6 |
| piper | ru | ipa | 6 | 5/6 |
| piper | ru | plain | 7 | 5/6 |
| qwen3_clone | it_a1 | plain | 10 | 0/0 |
| qwen3_clone | it_context | accent | 8 | 8/8 |
| qwen3_clone | it_context | plain | 8 | 8/8 |
| qwen3_clone | ru | accent | 6 | 6/6 |
| qwen3_clone | ru | plain | 7 | 5/6 |
| qwen3_voice | it_a1 | plain | 10 | 0/0 |
| qwen3_voice | it_context | accent | 8 | 7/7 |
| qwen3_voice | it_context | plain | 8 | 7/7 |
| qwen3_voice | it_gem | accent | 14 | 11/13 |
| qwen3_voice | it_gem | plain | 14 | 11/13 |
| qwen3_voice | it_solo | accent | 10 | 6/9 |
| qwen3_voice | it_solo | plain | 10 | 2/2 |
| qwen3_voice | it_stress | accent | 12 | 11/11 |
| qwen3_voice | it_stress | plain | 12 | 9/12 |
| qwen3_voice | ru | accent | 6 | 6/6 |
| qwen3_voice | ru | plain | 7 | 3/4 |
