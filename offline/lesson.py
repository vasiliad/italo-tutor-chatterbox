#!/usr/bin/env python3
"""Офлайн-урок Паоло «в бою»: уши (ASR) → мозг (LLM) → ударения → голос (TTS), всё локально на Mac.

Компоненты переключаются флагами — так сравниваем варианты на одном и том же уроке:
  --brain  qwen35-9b | gemma4-e4b | gemma4-12b            (mlx-lm, 4 бита)
  --voice  qwen3tts | kokoro-piper                          (mlx-audio 8 бит | sherpa-onnx: Kokoro it + Piper ru)
  --ears   parakeet | nemotron | qwen3asr-0.6b | qwen3asr-1.7b | whisper-turbo
           (Parakeet — sherpa-onnx int8; остальные — mlx-audio STT; язык везде определяется сам)
Голос начинает говорить с первого готового предложения, пока мозг дописывает остальное (Player в фоне).

Режимы:
  --live                 — урок с микрофона: Enter — начать говорить, Enter — закончить; «стоп» — конец урока.
  --scenario FILE.json   — реплики ученицы из сценария: озвучиваются Kokoro (it) / Piper (ru) и идут через те же уши,
                           как если бы она говорила в микрофон; одинаковый урок для всех сочетаний.
Итог: runs/<brain>__<voice>__<ears>[__<tag>]__<время>/ — log.jsonl (текст, задержки по этапам),
wav/NN_teacher.wav, NN_student.wav. reply_latency_s — от конца речи ученицы до первого звука учителя.

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
WHISPER_PROCESSOR = "openai/whisper-large-v3-turbo"
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

    def reply_stream(self, student_text, stats):
        """Реплика по предложениям: каждое готовое предложение отдаётся сразу — голос начинает говорить,
        пока мозг дописывает остальное. В stats — задержки мозга; полный текст — в историю."""
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        self.history.append({"role": "user", "content": student_text})
        msgs = [{"role": "system", "content": self.system}] + self._window()
        try:  # Qwen3.5: без «размышлений» в диалоге
            prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        except TypeError:
            prompt = self.tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        t0, first, first_sent, text, ntok, sent = time.time(), None, None, "", 0, 0
        if self.vlm is not None:
            from mlx_vlm import stream_generate as vlm_stream
            gen = vlm_stream(self.model, self.vlm, prompt, max_tokens=220, temperature=0.7, top_p=0.8)
        else:
            gen = stream_generate(self.model, self.tok, prompt, max_tokens=220, sampler=make_sampler(temp=0.7, top_p=0.8))
        llm_s = 0.0  # чистое время мозга (без пауз на озвучку)
        t_last = time.time()
        for r in gen:
            llm_s += time.time() - t_last
            if first is None:
                first = time.time() - t0
            text += r.text
            ntok += 1
            clean = _clean(text)
            m = None
            for m in SENT_END.finditer(clean, sent):
                pass
            if m is not None and m.end() > sent and "<think>" not in text.split("</think>")[-1]:
                chunk, sent = clean[sent:m.end()].strip(), m.end()
                if chunk:
                    if first_sent is None:
                        first_sent = round(time.time() - t0, 2)
                    yield chunk
            t_last = time.time()
        llm_s += time.time() - t_last
        clean = _clean(text)
        if clean[sent:].strip():
            if first_sent is None:
                first_sent = round(time.time() - t0, 2)
            yield clean[sent:].strip()
        self.history.append({"role": "assistant", "content": clean})
        stats.update(teacher=clean, llm_first_tok_s=round(first or llm_s, 2), llm_first_sentence_s=first_sent,
                     llm_total_s=round(llm_s, 2), llm_tok_s=round(ntok / max(llm_s, 1e-3), 1))


class ServerBrain(Brain):
    """Мозг через llama-server (llama.cpp) — для Windows/без видеокарты: GGUF на процессоре.
    llama-server держит KV-кэш диалога (cache_prompt), так что каждая реплика досчитывает только новые токены.
      llama-server -m gemma-4-E4B_q4_0-it.gguf -c 8192 -t <ядра> --port 8088
    --brain server[:http://127.0.0.1:8088]"""

    def __init__(self, url):
        self.name, self.repo, self.url = "server", url, url.rstrip("/")
        self.system = open(os.path.join(HERE, "paolo_offline_system.txt")).read()
        self.history = []
        self._warmup()

    def _warmup(self):
        """Инструкция Паоло (~800 токенов) на процессоре считается ~20 с — считаем её до урока,
        дальше llama-server берёт её из кэша."""
        import urllib.request
        body = json.dumps(dict(messages=[{"role": "system", "content": self.system}, {"role": "user", "content": "Ciao"}],
                               max_tokens=1, cache_prompt=True, chat_template_kwargs={"enable_thinking": False})).encode()
        t0 = time.time()
        urllib.request.urlopen(urllib.request.Request(self.url + "/v1/chat/completions", body,
                                                      {"Content-Type": "application/json"})).read()
        print(f"мозг прогрет: {time.time() - t0:.1f} с", file=sys.stderr)

    def reply_stream(self, student_text, stats):
        import urllib.request
        self.history.append({"role": "user", "content": student_text})
        msgs = [{"role": "system", "content": self.system}] + self._window()
        body = json.dumps(dict(messages=msgs, stream=True, max_tokens=220, temperature=0.7, top_p=0.8,
                               cache_prompt=True, chat_template_kwargs={"enable_thinking": False})).encode()
        req = urllib.request.Request(self.url + "/v1/chat/completions", body, {"Content-Type": "application/json"})
        t0, first, first_sent, text, ntok, sent, pause = time.time(), None, None, "", 0, 0, 0.0
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                line = line.decode().strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                d = json.loads(line[6:])
                delta = (d.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                if not delta:
                    continue
                if first is None:
                    first = time.time() - t0
                text += delta
                ntok += 1
                clean = _clean(text)
                m = None
                for m in SENT_END.finditer(clean, sent):
                    pass
                if m is not None and m.end() > sent:
                    chunk, sent = clean[sent:m.end()].strip(), m.end()
                    if chunk:
                        if first_sent is None:
                            first_sent = round(time.time() - t0, 2)
                        tp = time.time()
                        yield chunk  # сервер продолжает генерацию, пока мы озвучиваем
                        pause += time.time() - tp
        clean = _clean(text)
        if clean[sent:].strip():
            if first_sent is None:
                first_sent = round(time.time() - t0, 2)
            yield clean[sent:].strip()
        self.history.append({"role": "assistant", "content": clean})
        total = time.time() - t0
        stats.update(teacher=clean, llm_first_tok_s=round(first or total, 2), llm_first_sentence_s=first_sent,
                     llm_total_s=round(total, 2), llm_tok_s=round(ntok / max(total - pause, 1e-3), 1))


def _window(self):
    """История для мозга. Не сдвигаем окно на каждой реплике: сдвиг меняет начало промпта, и llama.cpp
    пересчитывает весь разговор заново (на процессоре — 15+ с). Обрезаем редко и сразу половину."""
    if len(self.history) > 48:
        del self.history[:24]
    return self.history


Brain._window = _window


SENT_END = re.compile(r"[.!?…]+[»\"')]*(?=\s)|\n+")


def _clean(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return re.sub(r"<turn\|>|<end_of_turn>|<\|?[a-z_]+\|?>", "", text).lstrip()


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


FEM = [(r"\b([Bb])ravo\b", r"\1rava"), (r"\b([Bb])ravissimo\b", r"\1ravissima"),
       (r"\b([Bb])envenuto\b", r"\1envenuta"), (r"\b([Ss])ei pronto\b", r"\1ei pronta")]


def to_feminine(text):
    """Ученица — девушка: Bravo → Brava и т.п. (мозг путает род, хоть это и есть в инструкции)."""
    for a, b in FEM:
        text = re.sub(a, b, text)
    return text


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
        # fp32 на x86 втрое быстрее int8 (RTF 0.43 против 1.25 на 4 ядрах Xeon) — если скачан, берём его
        k = os.path.join(MODELS, "kokoro-multi-lang-v1_0")
        kmodel = "model.onnx"
        if not os.path.exists(os.path.join(k, kmodel)):
            k, kmodel = os.path.join(MODELS, "kokoro-int8-multi-lang-v1_0"), "model.int8.onnx"
        th = int(os.environ.get("TTS_THREADS", "4"))
        ru = "dmitri" if male else "irina"
        self.sid = 36 if male else 35  # kokoro v1_0: 35 if_sara, 36 im_nicola
        p = os.path.join(MODELS, f"vits-piper-ru_RU-{ru}-medium")
        self.it = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
            kokoro=so.OfflineTtsKokoroModelConfig(model=f"{k}/{kmodel}", voices=f"{k}/voices.bin",
                                                  tokens=f"{k}/tokens.txt", data_dir=f"{k}/espeak-ng-data", lang="it"),
            num_threads=th)))
        self.ru = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
            vits=so.OfflineTtsVitsModelConfig(model=f"{p}/ru_RU-{ru}-medium.onnx", tokens=f"{p}/tokens.txt",
                                              data_dir=f"{p}/espeak-ng-data"), num_threads=th)))

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
EARS = {
    # Parakeet v3 (sherpa-onnx): числа пишет цифрами — «quatro» превращается в «4», ошибку не видно
    "parakeet": None,
    # остальные — mlx-audio STT
    "nemotron": "mlx-community/nemotron-3.5-asr-streaming-0.6b",
    "qwen3asr-0.6b": "mlx-community/Qwen3-ASR-0.6B-8bit",
    "qwen3asr-1.7b": "mlx-community/Qwen3-ASR-1.7B-8bit",
    "whisper-turbo": "mlx-community/whisper-large-v3-turbo",
    # Windows/без видеокарты: Qwen3-ASR GGUF в отдельном llama-server (ASR_URL, по умолчанию :8089)
    #   llama-server -m Qwen3-ASR-0.6B-Q8_0.gguf --mmproj mmproj-Qwen3-ASR-0.6B-Q8_0.gguf -c 4096 --port 8089
    # 4 ядра Xeon: 0.6B — 1.0 с/фраза, 33/39 буквально; 1.7B — 2.2 с, 34/39 (Parakeet: 0.3 с, 21/39)
    "server-asr": None,
}
ASR_CONTEXT = "Paolo, Паоло, Anna. Урок итальянского: ученица может ошибаться — quatro, anno. Пиши дословно, как сказано."
# подсказки распознаванию: имя учителя и слова урока (Qwen3-ASR и Whisper их понимают)
HOTWORDS = ["Paolo", "Паоло", "Anna", "vorrei", "caffè", "per favore", "quanto costa", "mi chiamo"]


class Ears:
    """Уши на выбор (--ears). Язык — автоопределение: ученица говорит то по-итальянски, то по-русски."""

    def __init__(self, name="parakeet"):
        self.name = name
        if name == "server-asr":
            self.url = os.environ.get("ASR_URL", "http://127.0.0.1:8089").rstrip("/")
        elif name == "parakeet":
            import sherpa_onnx as so
            d = os.path.join(MODELS, "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8")
            self.rec = so.OfflineRecognizer.from_transducer(
                encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx", joiner=f"{d}/joiner.int8.onnx",
                tokens=f"{d}/tokens.txt", model_type="nemo_transducer", num_threads=4)
        else:
            from mlx_audio.stt.utils import load
            self.model = load(EARS[name])
            if name == "whisper-turbo" and getattr(self.model, "_processor", None) is None:
                # в mlx-community/whisper-large-v3-turbo нет токенизатора — берём у openai (setup.sh докачивает)
                from transformers import WhisperProcessor
                self.model._processor = WhisperProcessor.from_pretrained(WHISPER_PROCESSOR)

    def hear(self, y16k):
        t0 = time.time()
        if self.name == "server-asr":
            import base64
            import io
            import urllib.request
            buf = io.BytesIO()
            sf.write(buf, y16k, 16000, format="WAV")
            msgs = [{"role": "system", "content": ASR_CONTEXT},
                    {"role": "user", "content": [{"type": "input_audio", "input_audio": {
                        "data": base64.b64encode(buf.getvalue()).decode(), "format": "wav"}}]}]
            body = json.dumps(dict(messages=msgs, temperature=0, max_tokens=160)).encode()
            r = json.load(urllib.request.urlopen(urllib.request.Request(
                self.url + "/v1/chat/completions", body, {"Content-Type": "application/json"})))
            text = r["choices"][0]["message"]["content"].split("<asr_text>")[-1]
        elif self.name == "parakeet":
            s = self.rec.create_stream()
            s.accept_waveform(16000, y16k)
            self.rec.decode_stream(s)
            text = s.result.text
        else:
            import mlx.core as mx
            y = mx.array(y16k.astype(np.float32))
            if self.name == "nemotron":
                r = self.model.generate(y, language="auto")
            elif self.name.startswith("qwen3asr"):
                r = self.model.generate(y, hotwords=HOTWORDS)
            else:  # whisper: без условия на прошлый текст — меньше «додумывания»
                r = self.model.generate(y, condition_on_previous_text=False, temperature=0.0,
                                        initial_prompt="Paolo, Anna. Ciao! Привет, Паоло.")
            text = getattr(r, "text", None) or str(r)
        return text.strip(), round(time.time() - t0, 2)


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


class Player:
    """Проигрывает куски по очереди в фоне: первое предложение звучит, пока готовятся следующие."""

    def __init__(self, enabled):
        import queue
        import threading
        self.q = queue.Queue()
        self.enabled = enabled
        if enabled:
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import sounddevice as sd
        while True:
            y, sr = self.q.get()
            try:
                sd.play(y, sr)
                sd.wait()
            except Exception as e:
                print(f"[нет воспроизведения: {e}]", file=sys.stderr)
            self.q.task_done()

    def put(self, y, sr):
        if self.enabled:
            self.q.put((y, sr))

    def wait(self):
        if self.enabled:
            self.q.join()


def speak(voice, text, sr_out=24000):
    """Текст с кусками на разных языках → один звук (каждый кусок своим голосом)."""
    parts = []
    for lang, chunk in split_lang(text):
        y, sr = voice.say(lang, chunk)
        parts += [resample(y, sr, sr_out), np.zeros(int(0.12 * sr_out), np.float32)]
    return np.concatenate(parts) if parts else np.zeros(1, np.float32)


# ---------------------------------------------------------------- урок
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brain", required=True, help=f"{' | '.join(BRAINS)} | server[:URL] (llama-server, Windows)")
    ap.add_argument("--voice", choices=["qwen3tts", "kokoro-piper"], required=True)
    ap.add_argument("--ears", choices=EARS, default="parakeet")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--live", action="store_true")
    g.add_argument("--scenario")
    g.add_argument("--student", choices=["gemini"], help="ученицу играет Gemini (текст + голос с акцентом), нужна сеть")
    ap.add_argument("--turns", type=int, default=12, help="реплик ученицы в режиме --student")
    ap.add_argument("--judge", action="store_true", help="после урока Паоло (Gemini REST) оценивает реплики и урок")
    ap.add_argument("--no-play", action="store_true", help="не проигрывать звук (сценарий в фоне)")
    ap.add_argument("--tag", default="", help="метка прогона в имени папки")
    a = ap.parse_args()

    run = os.path.join(HERE, "runs", "__".join([a.brain.split(":")[0], a.voice, a.ears] + ([a.tag] if a.tag else [])
                                               + [time.strftime("%m%d-%H%M")]))
    os.makedirs(os.path.join(run, "wav"), exist_ok=True)
    t = time.time()
    ears, stress = Ears(a.ears), Stress()
    voice = QwenVoice() if a.voice == "qwen3tts" else SherpaVoices()
    if a.brain.startswith("server"):
        brain = ServerBrain(a.brain.partition(":")[2] or "http://127.0.0.1:8088")
    elif a.brain in BRAINS:
        brain = Brain(a.brain)
    else:
        sys.exit(f"неизвестный мозг: {a.brain}")
    student_voice = SherpaVoices(male=False) if a.scenario else None  # «ученица» в сценарии: Kokoro it / Piper ru
    gstudent = None
    if a.student:
        from gemini_student import GeminiStudent
        gstudent = GeminiStudent()
    player = Player(not a.no_play)
    load_s = round(time.time() - t, 1)
    log = open(os.path.join(run, "log.jsonl"), "w")
    log.write(json.dumps(dict(event="start", brain=brain.repo, voice=a.voice, ears=a.ears, load_s=load_s), ensure_ascii=False) + "\n")
    print(f"загрузка {load_s} с; урок: {run}")

    turns = json.load(open(a.scenario))["turns"] if a.scenario else None
    n, sr_out, last_teacher, all_turns = 0, 24000, None, []
    while True:
        n += 1
        intended_error = None
        if gstudent is not None:
            if n > a.turns:
                break
            try:
                d = gstudent.reply(last_teacher)
                y, sr = gstudent.speak(d["say"])
            except Exception as e:  # лимиты Gemini — урок обрываем, оценку того, что есть, всё равно делаем
                print(f"[ученица-Gemini недоступна: {e} — урок окончен на реплике {n - 1}]", flush=True)
                break
            y16 = resample(y, sr, 16000)
            said, intended_error = d["say"], d.get("error")
        elif turns is not None:
            if n > len(turns):
                break
            tu = turns[n - 1]
            # смешанную реплику каждый язык говорит своим голосом (раньше Piper ru читал и итальянский кусок)
            y16 = resample(speak(student_voice, tu["text"]), sr_out, 16000)
            said = tu["text"]
        else:
            player.wait()
            y16 = record_until_enter()
            said = None
        sf.write(os.path.join(run, "wav", f"{n:02d}_student.wav"), y16, 16000)
        t_end = time.time()  # ученица закончила говорить
        heard, asr_s = ears.hear(y16)
        print(f"\nУченица{' (сценарий)' if said else ''}: {heard}" + (f"   [сказала: {said}]" if said and said != heard else "")
              + (f"   [ошибка: {intended_error}]" if intended_error else ""))
        if turns is None and re.search(r"\bстоп\b", heard.lower()):
            break
        st, audio, sents, first_audio, tts_s = {}, [], [], None, 0.0
        for sent in brain.reply_stream(heard or "(тишина — ученица ничего не сказала)", st):
            marked = stress.mark(to_feminine(sent))
            t1 = time.time()
            y = speak(voice, marked, sr_out)
            tts_s += time.time() - t1
            if first_audio is None:
                first_audio = round(time.time() - t_end, 2)  # от конца речи ученицы до первого звука
            player.put(y, sr_out)
            audio.append(y)
            sents.append(marked)
            print(f"Паоло: {marked}", flush=True)
        wav = np.concatenate(audio) if audio else np.zeros(1, np.float32)
        sf.write(os.path.join(run, "wav", f"{n:02d}_teacher.wav"), wav, sr_out)
        last_teacher = st.get("teacher") or " ".join(sents)
        rec = dict(event="turn", n=n, student_said=said, intended_error=intended_error, heard=heard, asr_s=asr_s, marked=" ".join(sents),
                   sentences=len(sents), tts_s=round(tts_s, 2), audio_s=round(len(wav) / sr_out, 2),
                   reply_latency_s=first_audio, **st)
        log.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.flush()
        all_turns.append(rec)
        print(f"  [уши {asr_s} с · мозг до 1-го предложения {st.get('llm_first_sentence_s')} с, всего {st.get('llm_total_s')} с "
              f"({st.get('llm_tok_s')} ток/с) · голос {rec['tts_s']} с · до первого звука {first_audio} с]")
    player.wait()
    try:  # на Windows нет resource
        import resource
        peak = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**30 if sys.platform == "darwin" else 2**20), 2)
    except ImportError:
        peak = None
    log.write(json.dumps(dict(event="end", peak_rss_gb=peak),
                         ensure_ascii=False) + "\n")
    if a.judge and all_turns:
        from gemini_student import judge_lesson, judge_turn
        scores = []
        for t in all_turns:
            try:
                j = judge_turn(t["student_said"] or t["heard"], t.get("intended_error"),
                               open(os.path.join(run, "wav", f"{t['n']:02d}_teacher.wav"), "rb").read())
            except Exception as e:
                j = {"score": None, "comment": f"[судья недоступен: {e}]"}
            j["n"] = t["n"]
            scores.append(j)
            print(f"Паоло-судья #{t['n']}: {j.get('score')} {j.get('comment', '')}", flush=True)
        try:
            lesson = judge_lesson(all_turns)
        except Exception as e:
            lesson = {"score": None, "comment": f"[судья недоступен: {e}]"}
        print(f"Урок целиком: {json.dumps(lesson, ensure_ascii=False)}")
        json.dump(dict(turns=scores, lesson=lesson), open(os.path.join(run, "judge.json"), "w"), ensure_ascii=False, indent=1)
    print(f"готово: {run}")


if __name__ == "__main__":
    main()
