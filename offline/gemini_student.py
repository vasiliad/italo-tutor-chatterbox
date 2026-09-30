"""Ученица и судья для боя без человека — ТОЛЬКО через Live API: gemini-3.8-live, запасная gemini-3.1-flash-live
(правило владельца 29.09: других моделей Google в проекте нет). Live отвечает голосом; текст берём из расшифровки,
поэтому ответы просим строками через « | », а не JSON.

Ученица (Анна, A1): отвечает на то, что реально сказал офлайн-Паоло, делает типичные ошибки русских
начинающих, иногда переходит на русский. Её голос — голос Live-модели (женский, с русским акцентом по инструкции),
так уши проверяются на «чужом» голосе.
Судья — Паоло (tools/expert/paolo_system.txt): оценивает каждую реплику учителя по звуку и урок целиком по тексту.
Ключи: GEMINI_API_KEY или ~/key/key (по кругу при сбое/лимите).
"""
import asyncio
import base64
import io
import json
import os
import re
import time

import numpy as np
import soundfile as sf
import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
URL = ("wss://generativelanguage.googleapis.com/ws/"
       "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")
MODELS = ["models/gemini-3.8-live", "models/gemini-3.1-flash-live-preview"]


def _keys():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return [k]
    p = os.path.expanduser("~/key/key")
    if os.path.exists(p):
        ks = open(p).read().split()
        if ks:
            return ks
    return [None]


KEYS = _keys()
_ki = [0]


async def _live_once(key, model, text, system, voice, audio16k, timeout):
    headers = {"x-goog-api-key": key} if key else {}
    async with websockets.connect(URL, additional_headers=headers, max_size=None, open_timeout=30) as ws:
        setup = {"model": model, "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}, "outputAudioTranscription": {}}
        if audio16k is not None:
            setup["realtimeInputConfig"] = {"automaticActivityDetection": {"disabled": True}}
        if system:
            setup["systemInstruction"] = {"parts": [{"text": system}]}
        await ws.send(json.dumps({"setup": setup}))
        first = json.loads(await asyncio.wait_for(ws.recv(), 30))
        if "setupComplete" not in first:
            raise RuntimeError(f"setup: {str(first)[:200]}")
        if audio16k is None:
            await ws.send(json.dumps({"realtimeInput": {"text": text}}))
        else:
            pcm = (np.clip(audio16k, -1, 1) * 32767).astype("<i2").tobytes()
            await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
            await ws.send(json.dumps({"realtimeInput": {"text": text}}))
            for i in range(0, len(pcm), 32000):
                await ws.send(json.dumps({"realtimeInput": {"audio": {
                    "mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(pcm[i:i + 32000]).decode()}}}))
            await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))
        words, audio = [], bytearray()
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            if "error" in m or "goAway" in m:
                raise RuntimeError(str(m)[:200])
            sc = m.get("serverContent") or {}
            for part in (sc.get("modelTurn") or {}).get("parts", []):
                inl = part.get("inlineData") or {}
                if inl.get("mimeType", "").startswith("audio/"):
                    audio += base64.b64decode(inl["data"])
            t = (sc.get("outputTranscription") or {}).get("text")
            if t:
                words.append(t)
            if sc.get("turnComplete"):
                return "".join(words).strip(), bytes(audio)


def live(text, system="", voice="Aoede", audio16k=None, timeout=60, tries=4):
    """→ (расшифровка ответа, PCM16 24 кГц). Ключи и модели по кругу при сбое/лимите."""
    last = None
    for i in range(tries):
        key = KEYS[_ki[0] % len(KEYS)]
        model = MODELS[(i // max(1, len(KEYS))) % len(MODELS)]
        try:
            return asyncio.run(_live_once(key, model, text, system, voice, audio16k, timeout))
        except Exception as e:
            last = e
            _ki[0] += 1
            print(f"[live {model.split('/')[-1]}: {str(e)[:120]} — повтор]", flush=True)
            time.sleep(3 + 5 * (i // max(1, len(KEYS))))
    raise RuntimeError(f"Live не ответил: {last}")


def fields(text, n):
    """«А | Б | В» → [А, Б, В] (ровно n полей; метки вида «СКАЖУ:» снимаются)."""
    parts = [re.sub(r"^\s*[А-ЯA-Zа-яa-zё ]{2,14}:\s*", "", p).strip() for p in text.split("|")]
    return (parts + [""] * n)[:n]


STUDENT_SYSTEM = """Ты играешь ученицу на уроке итальянского. Ты — Анна, 28 лет, из Москвы, русская, итальянский учишь
с нуля (A1), знаешь пока совсем немного слов. Учитель — Паоло, итальянец.

Как ты себя ведёшь:
- Отвечаешь коротко (одна короткая фраза, иногда два-три слова), как живой начинающий человек.
- Стараешься говорить по-итальянски, но примерно в каждой третьей реплике делаешь типичную ошибку русских
  начинающих: род и артикль (una caffè, il pizza), essere/avere (io sono venti anni, io ho venti anno),
  окончания глаголов (io parla, tu parlo), пропуск артикля, русский порядок слов, похожее слово не то.
- Иногда (примерно каждая пятая реплика) говоришь по-русски: не поняла, просишь повторить или перевести,
  смешиваешь («Да, vorrei… как будет „чай“?»).
- Если учитель исправил тебя — пробуешь повторить правильно (иногда снова с ошибкой).
- Не будь идеальной ученицей и не хвали учителя.

Ответ произнеси РОВНО одной строкой из трёх полей через « | », больше ничего:
СКАЖУ: что ты говоришь вслух | ЯЗЫК: it, ru или mix | ОШИБКА: какую ошибку ты сделала нарочно, по-русски, или «нет»"""


class GeminiStudent:
    def __init__(self, voice="Aoede"):
        self.voice = voice
        self.dialog = []  # (кто, текст)

    def reply(self, teacher_text):
        if teacher_text is not None:
            self.dialog.append(("Паоло", teacher_text))
        hist = "\n".join(f"{who}: {t}" for who, t in self.dialog) or "(урок только начинается)"
        prompt = (f"Разговор на уроке до этого момента:\n{hist}\n\n"
                  + ("Паоло ещё ничего не сказал — поздоровайся с ним." if teacher_text is None
                     else "Ответь Паоло как Анна."))
        raw, _ = live(prompt, system=STUDENT_SYSTEM, voice=self.voice)
        say, lang, err = fields(raw, 3)
        say = say.strip("«»\"' ") or raw
        err = None if not err or err.lower().startswith("нет") else err
        d = {"say": say, "lang": lang.lower() if lang.lower() in ("it", "ru", "mix") else "it", "error": err}
        self.dialog.append(("Анна", d["say"]))
        return d

    def speak(self, text):
        """Голос Анны: Live-модель читает текст с русским акцентом, ошибки не исправляет. → (float32, 24000)"""
        system = ("Ты — Анна, молодая русская женщина, только начала учить итальянский. Тебе дают реплику — произнеси "
                  "её вслух РОВНО как написано: с сильным русским акцентом, чуть медленно и неуверенно. НЕ исправляй "
                  "ошибок, ничего не добавляй и не отвечай на неё.")
        for _ in range(2):
            _, pcm = live(f"Произнеси: {text}", system=system, voice=self.voice)
            if pcm:
                return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768, 24000
        raise RuntimeError("Live не дал звука для реплики ученицы")


# ---------------------------------------------------------------- судья
def _paolo_system():
    p = os.path.join(HERE, "..", "tools", "expert", "paolo_system.txt")
    return open(p).read() if os.path.exists(p) else "Ты — Паоло, опытный учитель итальянского."


TURN_Q = ("Это слепая проверка офлайн-учителя итальянского для нашей школы (работает без интернета). "
          "Ученица (A1, русская) сказала: «{said}»{err}. Сейчас ты услышишь ответ учителя. Оцени как коллега: "
          "правильность итальянского, произношение и ударения, естественность голоса, и хорош ли это ответ учителя "
          "(по делу, коротко, заметил ли и исправил ли ошибку ученицы, не придумал ли ошибку, которой не было). "
          "Произнеси РОВНО одну строку: ОЦЕНКА: число от 1 до 5 | ЗАМЕТИЛ ОШИБКУ: да, нет или ошибки не было | "
          "КОММЕНТАРИЙ: одна-две фразы по-русски")


def _to16k(wav_bytes):
    y, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != 16000:
        n = int(len(y) * 16000 / sr)
        y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y).astype(np.float32)
    return y


def _score(s):
    m = re.search(r"[1-5]", s or "")
    return int(m.group(0)) if m else None


def judge_turn(said, intended_error, wav_bytes):
    err = f" (в реплике есть ошибка: {intended_error})" if intended_error else " (ошибки в реплике нет)"
    raw, _ = live(TURN_Q.format(said=said, err=err), system=_paolo_system(), voice="Algenib", audio16k=_to16k(wav_bytes))
    sc, caught, comment = fields(raw, 3)
    c = caught.lower()
    caught_v = True if c.startswith("да") else False if c.startswith("нет") else None
    return {"score": _score(sc), "caught_error": caught_v, "comment": comment or raw[:300]}


LESSON_Q = ("Вот запись урока офлайн-учителя итальянского (без интернета) с ученицей A1. «Ученица сказала» — что она "
            "сказала на самом деле, «уши услышали» — что распознал компьютер, «Учитель» — ответ.\n\n{log}\n\n"
            "Оцени урок целиком как опытный коллега: ведёт ли по плану, замечает ли ошибки, не придумывает ли их, "
            "понятно ли ученице, живой ли разговор. Произнеси РОВНО одну строку: ОЦЕНКА: число от 1 до 5 | "
            "ХОРОШО: … | ПЛОХО: … | ИСПРАВИТЬ: что изменить в инструкции учителя в первую очередь")


def judge_lesson(turns):
    log = "\n".join(f"Ученица сказала: {t['student_said']}\nУши услышали: {t['heard']}\nУчитель: {t['marked']}\n"
                    for t in turns)
    raw, _ = live(LESSON_Q.format(log=log), system=_paolo_system(), voice="Algenib")
    sc, good, bad, fix = fields(raw, 4)
    return {"score": _score(sc), "good": good, "bad": bad, "fix": fix, "raw": raw[:1500]}
