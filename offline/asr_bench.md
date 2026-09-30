# Выбор ушей: фразы ученицы (offline/asr_testset.json)

Источник звука: синтез Kokoro it / Piper ru (женские голоса). «Дошло буквально» — ошибки ученицы, имена и числа словами дошли до учителя как сказаны.

| уши | дошло буквально (keep) | фраз без потерь | точно слово в слово | время на фразу, с (медиана) | загрузка, с |
|---|---|---|---|---|---|
| parakeet | 21/39 | 11/20 | 9/20 | 0.08 | 1.3 |
| nemotron | 25/39 | 14/20 | 11/20 | 0.2 | 6.0 |
| qwen3asr-0.6b | 32/39 | 15/20 | 12/20 | 0.11 | 0.7 |
| qwen3asr-1.7b | 36/39 | 17/20 | 16/20 | 0.225 | 1.3 |
| whisper-turbo | 18/39 | 11/20 | 9/20 | 0.98 | 0.7 |

## Потери по фразам

- **Привет, Паоло! Я готова к уроку.** — parakeet: «Привет, Паула. Я готова к уроку.»; nemotron: «Привет, Паула! Я готова к уроку.»; qwen3asr-1.7b: «Привет, Паола. Я готова к уроку.»
- **Uno, due, tre, quatro, cinque.** — parakeet: «12345»; nemotron: «12345»; qwen3asr-0.6b: «Uno due tre quattro cinque»; qwen3asr-1.7b: «uno due tre quattro cinque»; whisper-turbo: «1, 2, 3, 4, 5.»
- **Sei, sette, otto, nove, dieci.** — parakeet: «6, 7, 8, 9, 10»; nemotron: «6 78 90»; whisper-turbo: «6, 7, 8, 9, 10.»
- **Io ho venti anno.** — parakeet: «Io 20 anno.»; nemotron: «Io venti anno.»; qwen3asr-0.6b: «Io venti anni.»; whisper-turbo: «Io 20 anno.»
- **Io sono venti anni.** — parakeet: «Io sono 20 anni.»
- **Vorrei un caffè, per favore.** — whisper-turbo: «Vorrei un caффе, per favore.»
- **Vorrei una caffè.** — whisper-turbo: «Ворои уна каффе.»
- **Quanto costa il caffè?** — whisper-turbo: «Которое, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Пастро, Па»
- **Lei è italiana? No, io sono russo.** — parakeet: «Lei è italiana, no io sono russa.»; whisper-turbo: «Лей е италиана? Ног, я соно руссо.»
- **Паоло, повтори, пожалуйста, медленнее.** — parakeet: «Паула, повтори, пожалуйста, медленнее.»; nemotron: «Паула повтори, пожалуйста, медленнее.»; qwen3asr-0.6b: «Паула повтори пожалуйста медленнее.»
- **Спасибо, Паоло! Grazie, a domani!** — parakeet: «Grazie a domani.»; nemotron: «Спасибо, Паула.  Грази о domani.»; qwen3asr-0.6b: «Svissi bo Paolo grazia domani»; qwen3asr-1.7b: «Grazie a domani.»; whisper-turbo: «Спасибо, Паоло. Грация, домани.»
- **Grazie mille! Это было очень полезно.** — parakeet: «Градссе, милле. Это было очень полезно.»; qwen3asr-0.6b: «Gracias, mille. Это было очень полезно.»
- **Mi piace molto la pizza e il gelato.** — whisper-turbo: «Ми пиаче мото ла пица и ла гелата.»
