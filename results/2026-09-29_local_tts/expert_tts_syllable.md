# Экспертиза на слух (models/gemini-3.8-live)

Верно — эксперт выбрал задуманное (ударение / слово / одна-две согласные). Оценка 1–5 — фразы A1.

## Итог по моделям (ударение и омографы it: it_solo + it_stress + it_context)

| модель | вариант | верно | % | геминаты | ru | he | оценка A1 |
|---|---|---|---|---|---|---|---|
| kokoro | accent | 17/27 | 63 | 10/13 |  |  | 5.0 |
| kokoro | ipa | 21/30 | 70 | 9/14 |  |  | 4.8 |
| kokoro | ipa_len | 0/0 |  | 9/14 |  |  |  |
| kokoro | plain | 23/28 | 82 | 9/13 |  |  | 4.9 |
| magpie | accent | 20/29 | 69 | 9/14 |  |  | 4.9 |
| magpie | plain | 18/27 | 67 | 9/13 |  |  | 4.9 |
| moss_v10 | accent | 23/27 | 85 | 5/11 | 3/4 |  | 5.0 |
| moss_v10 | clone | 0/0 |  |  | 3/6 |  | 5.0 |
| moss_v10 | ipa | 9/29 | 31 | 6/12 |  |  | 1.9 |
| moss_v10 | ipa_len | 0/0 |  | 7/13 |  |  |  |
| moss_v10 | ipa_len_word | 0/0 |  | 8/14 |  |  |  |
| moss_v10 | ipa_word | 13/27 | 48 | 6/14 | 4/6 |  |  |
| moss_v10 | plain | 20/28 | 71 | 5/13 | 2/5 |  | 4.9 |
| moss_v15 | accent | 19/26 | 73 | 7/11 | 2/6 |  | 4.9 |
| moss_v15 | clone | 0/0 |  |  | 2/5 |  | 4.9 |
| moss_v15 | ipa | 13/29 | 45 | 8/13 |  |  | 3.0 |
| moss_v15 | ipa_len | 0/0 |  | 6/11 |  |  |  |
| moss_v15 | ipa_len_word | 0/0 |  | 6/13 |  |  |  |
| moss_v15 | ipa_word | 17/26 | 65 | 7/13 | 3/6 |  |  |
| moss_v15 | plain | 17/27 | 63 | 10/13 | 4/6 |  | 5.0 |
| piper | accent | 18/27 | 67 | 8/12 | 2/6 |  | 4.9 |
| piper | ipa | 20/30 | 67 | 8/12 | 2/6 |  | 4.9 |
| piper | ipa_len | 0/0 |  | 6/13 |  |  |  |
| piper | plain | 20/30 | 67 | 11/13 | 4/6 |  | 5.0 |
| qwen3_clone | accent | 6/8 | 75 |  | 2/6 |  | 4.9 |
| qwen3_clone | plain | 6/7 | 86 |  | 3/6 |  | 5.0 |
| qwen3_voice | accent | 21/30 | 70 | 10/11 | 3/6 |  | 4.9 |
| qwen3_voice | plain | 22/29 | 76 | 9/13 | 3/6 |  | 4.9 |

## По разделам

| модель | раздел | вариант | n | верно / с эталоном |
|---|---|---|---|---|
| kokoro | it_a1 | accent | 10 | 0/0 |
| kokoro | it_a1 | ipa | 10 | 0/0 |
| kokoro | it_a1 | plain | 10 | 0/0 |
| kokoro | it_context | accent | 8 | 5/6 |
| kokoro | it_context | ipa | 8 | 7/8 |
| kokoro | it_context | plain | 8 | 8/8 |
| kokoro | it_gem | accent | 14 | 10/13 |
| kokoro | it_gem | ipa | 14 | 9/14 |
| kokoro | it_gem | ipa_len | 14 | 9/14 |
| kokoro | it_gem | plain | 14 | 9/13 |
| kokoro | it_solo | accent | 10 | 5/9 |
| kokoro | it_solo | ipa | 10 | 6/10 |
| kokoro | it_solo | plain | 10 | 7/9 |
| kokoro | it_stress | accent | 12 | 7/12 |
| kokoro | it_stress | ipa | 12 | 8/12 |
| kokoro | it_stress | plain | 12 | 8/11 |
| magpie | it_a1 | accent | 10 | 0/0 |
| magpie | it_a1 | plain | 10 | 0/0 |
| magpie | it_context | accent | 8 | 7/8 |
| magpie | it_context | plain | 8 | 5/8 |
| magpie | it_gem | accent | 14 | 9/14 |
| magpie | it_gem | plain | 14 | 9/13 |
| magpie | it_solo | accent | 10 | 6/10 |
| magpie | it_solo | plain | 10 | 5/9 |
| magpie | it_stress | accent | 12 | 7/11 |
| magpie | it_stress | plain | 12 | 8/10 |
| moss_v10 | it_a1 | accent | 10 | 0/0 |
| moss_v10 | it_a1 | clone | 10 | 0/0 |
| moss_v10 | it_a1 | ipa | 10 | 0/0 |
| moss_v10 | it_a1 | plain | 10 | 0/0 |
| moss_v10 | it_context | accent | 8 | 7/7 |
| moss_v10 | it_context | ipa | 8 | 1/7 |
| moss_v10 | it_context | ipa_word | 8 | 3/6 |
| moss_v10 | it_context | plain | 8 | 5/8 |
| moss_v10 | it_gem | accent | 14 | 5/11 |
| moss_v10 | it_gem | ipa | 14 | 6/12 |
| moss_v10 | it_gem | ipa_len | 14 | 7/13 |
| moss_v10 | it_gem | ipa_len_word | 14 | 8/14 |
| moss_v10 | it_gem | ipa_word | 14 | 6/14 |
| moss_v10 | it_gem | plain | 14 | 5/13 |
| moss_v10 | it_solo | accent | 10 | 4/8 |
| moss_v10 | it_solo | ipa | 10 | 6/10 |
| moss_v10 | it_solo | ipa_word | 10 | 5/9 |
| moss_v10 | it_solo | plain | 10 | 7/10 |
| moss_v10 | it_stress | accent | 12 | 12/12 |
| moss_v10 | it_stress | ipa | 12 | 2/12 |
| moss_v10 | it_stress | ipa_word | 12 | 5/12 |
| moss_v10 | it_stress | plain | 12 | 8/10 |
| moss_v10 | ru | accent | 6 | 3/4 |
| moss_v10 | ru | clone | 7 | 3/6 |
| moss_v10 | ru | ipa_word | 6 | 4/6 |
| moss_v10 | ru | plain | 7 | 2/5 |
| moss_v15 | it_a1 | accent | 10 | 0/0 |
| moss_v15 | it_a1 | clone | 10 | 0/0 |
| moss_v15 | it_a1 | ipa | 10 | 0/0 |
| moss_v15 | it_a1 | plain | 10 | 0/0 |
| moss_v15 | it_context | accent | 8 | 4/7 |
| moss_v15 | it_context | ipa | 8 | 5/8 |
| moss_v15 | it_context | ipa_word | 8 | 7/8 |
| moss_v15 | it_context | plain | 8 | 6/8 |
| moss_v15 | it_gem | accent | 14 | 7/11 |
| moss_v15 | it_gem | ipa | 14 | 8/13 |
| moss_v15 | it_gem | ipa_len | 14 | 6/11 |
| moss_v15 | it_gem | ipa_len_word | 14 | 6/13 |
| moss_v15 | it_gem | ipa_word | 14 | 7/13 |
| moss_v15 | it_gem | plain | 14 | 10/13 |
| moss_v15 | it_solo | accent | 10 | 5/8 |
| moss_v15 | it_solo | ipa | 10 | 3/9 |
| moss_v15 | it_solo | ipa_word | 10 | 5/8 |
| moss_v15 | it_solo | plain | 10 | 4/7 |
| moss_v15 | it_stress | accent | 12 | 10/11 |
| moss_v15 | it_stress | ipa | 12 | 5/12 |
| moss_v15 | it_stress | ipa_word | 12 | 5/10 |
| moss_v15 | it_stress | plain | 12 | 7/12 |
| moss_v15 | ru | accent | 6 | 2/6 |
| moss_v15 | ru | clone | 7 | 2/5 |
| moss_v15 | ru | ipa_word | 6 | 3/6 |
| moss_v15 | ru | plain | 7 | 4/6 |
| piper | it_a1 | accent | 10 | 0/0 |
| piper | it_a1 | ipa | 10 | 0/0 |
| piper | it_a1 | plain | 10 | 0/0 |
| piper | it_context | accent | 8 | 6/8 |
| piper | it_context | ipa | 8 | 6/8 |
| piper | it_context | plain | 8 | 5/8 |
| piper | it_gem | accent | 14 | 8/12 |
| piper | it_gem | ipa | 14 | 8/12 |
| piper | it_gem | ipa_len | 14 | 6/13 |
| piper | it_gem | plain | 14 | 11/13 |
| piper | it_solo | accent | 10 | 5/9 |
| piper | it_solo | ipa | 10 | 5/10 |
| piper | it_solo | plain | 10 | 6/10 |
| piper | it_stress | accent | 12 | 7/10 |
| piper | it_stress | ipa | 12 | 9/12 |
| piper | it_stress | plain | 12 | 9/12 |
| piper | ru | accent | 6 | 2/6 |
| piper | ru | ipa | 6 | 2/6 |
| piper | ru | plain | 7 | 4/6 |
| qwen3_clone | it_a1 | accent | 10 | 0/0 |
| qwen3_clone | it_a1 | plain | 10 | 0/0 |
| qwen3_clone | it_context | accent | 8 | 6/8 |
| qwen3_clone | it_context | plain | 8 | 6/7 |
| qwen3_clone | ru | accent | 6 | 2/6 |
| qwen3_clone | ru | plain | 7 | 3/6 |
| qwen3_voice | it_a1 | accent | 10 | 0/0 |
| qwen3_voice | it_a1 | plain | 10 | 0/0 |
| qwen3_voice | it_context | accent | 8 | 5/8 |
| qwen3_voice | it_context | plain | 8 | 6/8 |
| qwen3_voice | it_gem | accent | 14 | 10/11 |
| qwen3_voice | it_gem | plain | 14 | 9/13 |
| qwen3_voice | it_solo | accent | 10 | 6/10 |
| qwen3_voice | it_solo | plain | 10 | 6/9 |
| qwen3_voice | it_stress | accent | 12 | 10/12 |
| qwen3_voice | it_stress | plain | 12 | 10/12 |
| qwen3_voice | ru | accent | 6 | 3/6 |
| qwen3_voice | ru | plain | 7 | 3/6 |
