#!/usr/bin/env python3
"""Офлайн-урок Паоло «в бою»: уши (ASR) → мозг (LLM) → ударения → голос (TTS), всё локально на Mac.

Компоненты переключаются флагами — так сравниваем варианты на одном и том же уроке:
  --brain  qwen35-9b | gemma4-e4b | gemma4-12b            (mlx-lm, 4 бита)
  --voice  qwen3tts | kokoro-piper                          (mlx-audio 8 бит | sherpa-onnx: Kokoro it + Piper ru)
  --ears   parakeet                                         (sherpa-onnx, Parakeet TDT 0.6B v3 int8, it+ru)

Режимы:
  --live                 — урок с микрофона: Enter — начать говорить, Enter — закончить; «стоп» — конец урока.
  --scenario FILE.json   — реплики ученицы из сценария: озвучиваются Piper (it/ru) и идут через те же уши,
                           как если бы она говорила в микрофон; одинаковый урок для всех сочетаний.
Итог: runs/<brain>__<voice>__<время>/ — log.jsonl (текст, задержки по этапам), wav/NN_teacher.wav, NN_student.wav.

  python offline/lesson.py --brain qwen35-9b --voice kokoro-piper --scenario offline/scenario_a1.json
  python offline/lesson.py --brain gemma4-12b --voice qwen3tts --live
Модели скачивает offline/setup.sh (один раз, с интернетом); дальше работает без сети (HF_HUB_OFFLINE=1).
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import unicodedata

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("OFFLINE_MODELS", os.path.expanduser("~/offline_models"))
BRAINS = {
    "qwen35-9b": "mlx-community/Qwen3.5-9B-4bit",
    "gemma4-e4b": "lmstudio-community/gemma-4-E4B-it-MLX-4bit",
    "gemma4-12b": "mlx-community/gemma-4-12B-it-4bit",
}
QWEN_TTS = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
QWEN_SPEAKER = os.environ.get("QWEN_SPEAKER", "Ryan")
CYR = re.compile(r"[А-Яа-яЁё]")


# ---------------------------------------------------------------- мозг
class Brain:
    def __init__(self, name):
        from pathlib import Path
        from huggingface_hub import snapshot_download
        from mlx_lm.utils import load_model, load_tokenizer
        self.name, self.repo = name, BRAINS[name]
        path = Path(snapshot_download(self.repo))
        self.vlm = None
        try:
            # Gemma 4: в весах lmstudio есть k/v последних слоёв, а mlx-lm делит KV между ними — лишние
            # веса отбрасываем (strict=False), иначе «parameters not in model»
            self.model, _ = load_model(path, strict=False)
            self.tok = load_tokenizer(path)
        except ValueError as e:
            # Gemma 4 12B — тип gemma4_unified: в mlx-lm 0.31 его нет, есть в mlx-vlm
            if "not supported" not in str(e):
                raise
            from mlx_vlm import load as vlm_load
            self.model, self.vlm = vlm_load(str(path))
            self.tok = self.vlm.tokenizer if hasattr(self.vlm, "tokenizer") else self.vlm
        # Gemma 4 заканчивает реплику токеном <turn|>, которого нет среди eos — без этого пишет до max_tokens
        if self.vlm is None:
            for t in ("<turn|>", "<end_of_turn>"):
                if t in self.tok.get_vocab():
                    self.tok.add_eos_token(t)
        self.system = open(os.path.join(HERE, "paolo_offline_system.txt")).read()
        self.history = []

    def reply(self, student_text):
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        self.history.append({"role": "user", "content": student_text})
        msgs = [{"role": "system", "content": self.system}] + self.history[-16:]
        try:  # Qwen3.5: без «размышлений» в диалоге
            prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        except TypeError:
            prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        t0, first, text, ntok = time.time(), None, "", 0
        if self.vlm is not None:
            from mlx_vlm import stream_generate as vlm_stream
            gen = vlm_stream(self.model, self.vlm, prompt, max_tokens=220, temperature=0.7, top_p=0.8)
        else:
            gen = stream_generate(self.model, self.tok, prompt, max_tokens=220, sampler=make_sampler(temp=0.7, top_p=0.8))
        for r in gen:
            if first is None:
                first = time.time() - t0
            text += r.text
            ntok += 1
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        text = re.sub(r"<turn\|>|<end_of_turn>|<\|?[a-z_]+\|?>", "", text).strip()
        self.history.append({"role": "assistant", "content": text})
        dt = time.time() - t0
        return text, dict(llm_first_s=round(first or dt, 2), llm_total_s=round(dt, 2), llm_tok_s=round(ntok / max(dt, 1e-3), 1))


# ---------------------------------------------------------------- ударения (итальянский)
class Stress:
    """Словарь ударений приложения (assets/lexicon/it_stress.tsv.gz, ~500 тыс. форм из Викисловаря):
    слово с одним вариантом получает знак ударения; омографы (несколько вариантов) оставляем как написал мозг."""

    def __init__(self):
        path = os.environ.get("IT_STRESS", os.path.join(HERE, "..", "..", "italo-tutor", "assets", "lexicon", "it_stress.tsv.gz"))
        self.lex = {}
        if os.path.exists(path):
            for line in gzip.open(path, "rt", encoding="utf-8"):
                k, _, v = line.rstrip("\n").partition("\t")
                self.lex[k] = v.split(",")
        print(f"словарь ударений: {len(self.lex)} форм", file=sys.stderr)

    def mark(self, text):
        def fix(m):
            w = m.group(0)
            if any(unicodedata.combining(c) for c in unicodedata.normalize("NFD", w)) or w[-1] in "àèéìíòóù":
                return w  # уже с ударением
            v = self.lex.get(w.lower())
            if not v or len(v) != 1 or sum(c in "aeiou" for c in w.lower()) < 2:
                return w
            out = v[0] if w.islower() else v[0][0].upper() + v[0][1:]
            return out
        return unicodedata.normalize("NFC", re.sub(r"[A-Za-zÀ-ÿ]+", fix, text))


def split_lang(text):
    """Куски по языку: кириллица → ru, остальное → it. Знаки препинания держатся со своим куском."""
    parts, cur, lang = [], "", None
    for tok in re.findall(r"\S+\s*", text):
        l = "ru" if CYR.search(tok) else ("it" if re.search(r"[A-Za-zÀ-ÿ]", tok) else lang)
        if lang is not None and l != lang and cur.strip():
            parts.append((lang, cur.strip()))
            cur = ""
        cur += tok
        lang = l or lang
    if cur.strip():
        parts.append((lang or "it", cur.strip()))
    return parts


# ---------------------------------------------------------------- голос
class SherpaVoices:
    """Kokoro int8 (it) и Piper ru через sherpa-onnx; у Piper ru — espeak-ng с русским ударением
    (tools/offline/espeak_ru_stress.sh в italo-tutor). Паоло — мужские голоса (im_nicola, dmitri),
    «ученица» в сценарии — женские (if_sara, irina)."""

    def __init__(self, male=True):
        import sherpa_onnx as so
        k = os.path.join(MODELS, "kokoro-int8-multi-lang-v1_0")
        ru = "dmitri" if male else "irina"
        self.sid = 36 if male else 35  # kokoro v1_0: 35 if_sara, 36 im_nicola
        p = os.path.join(MODELS, f"vits-piper-ru_RU-{ru}-medium")
        self.it = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
            kokoro=so.OfflineTtsKokoroModelConfig(model=f"{k}/model.int8.onnx", voices=f"{k}/voices.bin",
                                                  tokens=f"{k}/tokens.txt", data_dir=f"{k}/espeak-ng-data", lang="it"),
            num_threads=4)))
        self.ru = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
            vits=so.OfflineTtsVitsModelConfig(model=f"{p}/ru_RU-{ru}-medium.onnx", tokens=f"{p}/tokens.txt",
                                              data_dir=f"{p}/espeak-ng-data"), num_threads=4)))

    def say(self, lang, text):
        if lang == "it":
            a = self.it.generate(text, sid=self.sid, speed=0.95)
        else:
            a = self.ru.generate(text, sid=0, speed=1.0)
        return np.array(a.samples, dtype=np.float32), a.sample_rate


class QwenVoice:
    """Qwen3-TTS 1.7B CustomVoice (MLX 8 бит): it и ru одной моделью. Гвард от зацикливания: звук длиннее
    ~0.12 с на символ ×2 — переозвучить запасным голосом (Kokoro/Piper)."""

    def __init__(self):
        from mlx_audio.tts.utils import load_model
        self.model = load_model(QWEN_TTS)
        self.fallback = None

    def say(self, lang, text):
        chunks, sr = [], 24000
        for r in self.model.generate(text=text, voice=QWEN_SPEAKER, lang_code={"it": "italian", "ru": "russian"}[lang]):
            chunks.append(np.array(r.audio, dtype=np.float32))
            sr = getattr(r, "sample_rate", sr)
        y = np.concatenate(chunks) if chunks else np.zeros(1, np.float32)
        if len(y) / sr > max(3.0, 0.12 * len(text) * 2):
            if self.fallback is None:
                self.fallback = SherpaVoices()
            print(f"[зацикливание Qwen3-TTS: {len(y) / sr:.1f} с на {len(text)} симв. — запасной голос]", file=sys.stderr)
            return self.fallback.say(lang, text)
        return y, sr


def resample(y, sr, to):
    if sr == to:
        return y
    n = int(len(y) * to / sr)
    return np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y).astype(np.float32)


# ---------------------------------------------------------------- уши
class Ears:
    """Parakeet TDT 0.6B v3 int8 (sherpa-onnx): 25 языков, it и ru автоматически."""

    def __init__(self):
        import sherpa_onnx as so
        d = os.path.join(MODELS, "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8")
        self.rec = so.OfflineRecognizer.from_transducer(
            encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx", joiner=f"{d}/joiner.int8.onnx",
            tokens=f"{d}/tokens.txt", model_type="nemo_transducer", num_threads=4)

    def hear(self, y16k):
        t0 = time.time()
        s = self.rec.create_stream()
        s.accept_waveform(16000, y16k)
        self.rec.decode_stream(s)
        return s.result.text.strip(), round(time.time() - t0, 2)


def record_until_enter():
    import sounddevice as sd
    buf = []
    st = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=lambda d, *_: buf.append(d.copy()))
    input("  [Enter — говорить] ")
    st.start()
    input("  … говорите … [Enter — готово] ")
    st.stop()
    st.close()
    return np.concatenate(buf)[:, 0] if buf else np.zeros(1600, np.float32)


def play(y, sr):
    try:
        import sounddevice as sd
        sd.play(y, sr)
        sd.wait()
    except Exception as e:
        print(f"[нет воспроизведения: {e}]", file=sys.stderr)


# ---------------------------------------------------------------- урок
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", choices=BRAINS, required=True)
    ap.add_argument("--voice", choices=["qwen3tts", "kokoro-piper"], required=True)
    ap.add_argument("--ears", choices=["parakeet"], default="parakeet")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true")
    g.add_argument("--scenario")
    ap.add_argument("--no-play", action="store_true", help="не проигрывать звук (сценарий в фоне)")
    a = ap.parse_args()

    run = os.path.join(HERE, "runs", f"{a.brain}__{a.voice}__{time.strftime('%m%d-%H%M')}")
    os.makedirs(os.path.join(run, "wav"), exist_ok=True)
    t = time.time()
    ears, stress = Ears(), Stress()
    voice = QwenVoice() if a.voice == "qwen3tts" else SherpaVoices()
    brain = Brain(a.brain)
    student_voice = SherpaVoices(male=False) if a.scenario else None  # «ученица» в сценарии: Kokoro it / Piper ru
    load_s = round(time.time() - t, 1)
    log = open(os.path.join(run, "log.jsonl"), "w")
    log.write(json.dumps(dict(event="start", brain=brain.repo, voice=a.voice, ears=a.ears, load_s=load_s), ensure_ascii=False) + "\n")
    print(f"загрузка {load_s} с; урок: {run}")

    turns = json.load(open(a.scenario))["turns"] if a.scenario else None
    n = 0
    while True:
        n += 1
        if turns is not None:
            if n > len(turns):
                break
            tu = turns[n - 1]
            y, sr = student_voice.say(tu["lang"], tu["text"])
            y16 = resample(y, sr, 16000)
            said = tu["text"]
        else:
            y16 = record_until_enter()
            said = None
        sf.write(os.path.join(run, "wav", f"{n:02d}_student.wav"), y16, 16000)
        heard, asr_s = ears.hear(y16)
        print(f"\nУченица{' (сценарий)' if said else ''}: {heard}")
        if turns is None and re.search(r"\bстоп\b", heard.lower()):
            break
        text, st = brain.reply(heard or "(тишина — ученица ничего не сказала)")
        marked = stress.mark(text)
        t1, audio, sr_out = time.time(), [], 24000
        first_audio = None
        for lang, chunk in split_lang(marked):
            y, sr = voice.say(lang, chunk)
            if first_audio is None:
                first_audio = round(time.time() - t1, 2)
            audio.append(resample(y, sr, sr_out))
            audio.append(np.zeros(int(0.15 * sr_out), np.float32))
        wav = np.concatenate(audio) if audio else np.zeros(1, np.float32)
        tts_s = round(time.time() - t1, 2)
        sf.write(os.path.join(run, "wav", f"{n:02d}_teacher.wav"), wav, sr_out)
        rec = dict(event="turn", n=n, student_said=said, heard=heard, asr_s=asr_s, teacher=text, marked=marked,
                   tts_first_chunk_s=first_audio, tts_s=tts_s, audio_s=round(len(wav) / sr_out, 2),
                   reply_latency_s=round(asr_s + st["llm_total_s"] + (first_audio or 0), 2), **st)
        log.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.flush()
        print(f"Паоло: {marked}\n  [ASR {asr_s} с · LLM {st['llm_total_s']} с ({st['llm_tok_s']} ток/с) · "
              f"голос {tts_s} с · до первого звука ≈ {rec['reply_latency_s']} с]")
        if not a.no_play:
            play(wav, sr_out)
    import resource
    log.write(json.dumps(dict(event="end", peak_rss_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30, 2)),
                         ensure_ascii=False) + "\n")
    print(f"готово: {run}")


if __name__ == "__main__":
    main()
