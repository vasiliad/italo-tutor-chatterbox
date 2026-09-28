# Локальные TTS: сводка прогона

CER — Whisper large-v3-turbo к обычному тексту (разборчивость; ударение и долготу проверяет экспертиза).

| модель | загрузка, с | RTF (медиана) | RAM, ГБ | GPU, ГБ | записей | ошибок | CER it | CER ru | CER he |
|---|---|---|---|---|---|---|---|---|---|
| kokoro | 30.4 | 0.04 | 2.05 | 0.63 | 176 | 0 | 0.016 |  |  |
| magpie | 229.7 | 1.17 | 3.48 | 3.47 | 108 | 0 | 0.013 |  |  |
| moss_v10 | 96.7 | 3.63 | 12.67 | 5.78 | 270 | 0 | 0.317 | 0.203 |  |
| moss_v15 | 279.8 | 1.19 | 21.5 | 8.09 | 284 | 0 | 0.23 | 0.062 | 0.174 |
| piper | 3.0 | 0.07 | 0.85 | 0.0 | 195 | 0 | 0.049 | 0.012 |  |
| qwen3_clone | 37.7 | 2.25 | 7.76 | 8.49 | 49 | 0 | 0.014 | 0.037 |  |
| qwen3_voice | 61.3 | 2.24 | 7.75 | 8.66 | 121 | 0 | 0.451 | 0.027 |  |

## kokoro

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.025 |
| it_a1 | ipa | 10 | 0.025 |
| it_a1 | plain | 10 | 0.025 |
| it_context | accent | 8 | 0.0 |
| it_context | ipa | 8 | 0.0 |
| it_context | plain | 8 | 0.007 |
| it_gem | accent | 14 | 0.034 |
| it_gem | ipa | 14 | 0.034 |
| it_gem | ipa_len | 14 | 0.038 |
| it_gem | plain | 14 | 0.034 |
| it_solo | accent | 10 | 0.0 |
| it_solo | ipa | 10 | 0.0 |
| it_solo | plain | 10 | 0.0 |
| it_stress | accent | 12 | 0.0 |
| it_stress | ipa | 12 | 0.0 |
| it_stress | plain | 12 | 0.0 |

## magpie

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.025 |
| it_a1 | plain | 10 | 0.025 |
| it_context | accent | 8 | 0.0 |
| it_context | plain | 8 | 0.004 |
| it_gem | accent | 14 | 0.004 |
| it_gem | plain | 14 | 0.048 |
| it_solo | accent | 10 | 0.0 |
| it_solo | plain | 10 | 0.0 |
| it_stress | accent | 12 | 0.012 |
| it_stress | plain | 12 | 0.0 |

## moss_v10

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.035 |
| it_a1 | clone | 10 | 0.03 |
| it_a1 | ipa | 10 | 0.835 |
| it_a1 | plain | 10 | 0.031 |
| it_context | accent | 8 | 0.036 |
| it_context | ipa | 8 | 0.856 |
| it_context | ipa_word | 8 | 0.241 |
| it_context | plain | 8 | 0.047 |
| it_gem | accent | 14 | 0.054 |
| it_gem | ipa | 14 | 0.639 |
| it_gem | ipa_len | 14 | 0.716 |
| it_gem | ipa_len_word | 14 | 0.285 |
| it_gem | ipa_word | 14 | 0.383 |
| it_gem | plain | 14 | 0.051 |
| it_solo | accent | 10 | 0.092 |
| it_solo | ipa | 10 | 0.681 |
| it_solo | ipa_word | 10 | 0.282 |
| it_solo | plain | 10 | 0.044 |
| it_stress | accent | 12 | 0.063 |
| it_stress | ipa | 12 | 0.825 |
| it_stress | ipa_word | 12 | 0.449 |
| it_stress | plain | 12 | 0.149 |
| ru | accent | 6 | 0.03 |
| ru | clone | 7 | 0.461 |
| ru | ipa_word | 6 | 0.26 |
| ru | plain | 7 | 0.045 |

## moss_v15

| раздел | вариант | n | CER |
|---|---|---|---|
| he | niqqud | 7 | 0.217 |
| he | plain | 7 | 0.13 |
| it_a1 | accent | 10 | 0.025 |
| it_a1 | clone | 10 | 0.025 |
| it_a1 | ipa | 10 | 0.377 |
| it_a1 | plain | 10 | 0.028 |
| it_context | accent | 8 | 0.0 |
| it_context | ipa | 8 | 0.311 |
| it_context | ipa_word | 8 | 0.02 |
| it_context | plain | 8 | 0.012 |
| it_gem | accent | 14 | 0.255 |
| it_gem | ipa | 14 | 0.595 |
| it_gem | ipa_len | 14 | 0.815 |
| it_gem | ipa_len_word | 14 | 0.144 |
| it_gem | ipa_word | 14 | 0.052 |
| it_gem | plain | 14 | 0.137 |
| it_solo | accent | 10 | 0.129 |
| it_solo | ipa | 10 | 0.598 |
| it_solo | ipa_word | 10 | 0.131 |
| it_solo | plain | 10 | 0.179 |
| it_stress | accent | 12 | 0.143 |
| it_stress | ipa | 12 | 0.431 |
| it_stress | ipa_word | 12 | 0.26 |
| it_stress | plain | 12 | 0.047 |
| ru | accent | 6 | 0.0 |
| ru | clone | 7 | 0.002 |
| ru | ipa_word | 6 | 0.265 |
| ru | plain | 7 | 0.002 |

## piper

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.021 |
| it_a1 | ipa | 10 | 0.028 |
| it_a1 | plain | 10 | 0.053 |
| it_context | accent | 8 | 0.037 |
| it_context | ipa | 8 | 0.005 |
| it_context | plain | 8 | 0.009 |
| it_gem | accent | 14 | 0.048 |
| it_gem | ipa | 14 | 0.087 |
| it_gem | ipa_len | 14 | 0.113 |
| it_gem | plain | 14 | 0.068 |
| it_solo | accent | 10 | 0.059 |
| it_solo | ipa | 10 | 0.005 |
| it_solo | plain | 10 | 0.035 |
| it_stress | accent | 12 | 0.069 |
| it_stress | ipa | 12 | 0.048 |
| it_stress | plain | 12 | 0.032 |
| ru | accent | 6 | 0.017 |
| ru | ipa | 6 | 0.011 |
| ru | plain | 7 | 0.008 |

## qwen3_clone

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.025 |
| it_a1 | plain | 10 | 0.025 |
| it_context | accent | 8 | 0.0 |
| it_context | plain | 8 | 0.0 |
| ru | accent | 6 | 0.081 |
| ru | plain | 7 | 0.0 |

## qwen3_voice

| раздел | вариант | n | CER |
|---|---|---|---|
| it_a1 | accent | 10 | 0.036 |
| it_a1 | plain | 10 | 0.045 |
| it_context | accent | 8 | 0.003 |
| it_context | plain | 8 | 5.786 |
| it_gem | accent | 14 | 0.046 |
| it_gem | plain | 14 | 0.02 |
| it_solo | accent | 10 | 0.022 |
| it_solo | plain | 10 | 0.0 |
| it_stress | accent | 12 | 0.033 |
| it_stress | plain | 12 | 0.004 |
| ru | accent | 6 | 0.038 |
| ru | plain | 7 | 0.018 |
