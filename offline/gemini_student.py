"""Ученица и судья через Gemini REST (generateContent) — для боя без человека.

Ученица (Анна, A1): отвечает на то, что реально сказал офлайн-Паоло, делает типичные ошибки русских
начинающих, иногда переходит на русский. Её голос — Gemini TTS с русским акцентом (не наш синтез),
так уши проверяются на «чужом» голосе.
Судья — Паоло (tools/expert/paolo_system.txt): оценивает каждую реплику учителя по звуку и урок целиком по тексту.

Ключ: GEMINI_API_KEY или первый из ~/key/key; в облачном окружении ключ добавляет прокси.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://generativelanguage.googleapis.com/v1beta/models/"
# через запятую — запасные модели на случай 503 (перегрузка)
TEXT_MODEL = os.environ.get("STUDENT_MODEL", "gemini-3.8-flash,gemini-3.5-flash")
TTS_MODEL = os.environ.get("STUDENT_TTS", "gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini-3.8-flash,gemini-3.5-flash")


def _keys():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return [k]
    p = os.path.expanduser("~/key/key")
    if os.path.exists(p):
        ks = open(p).read().split()
        if ks:
            return ks
    return [None]  # облачное окружение: ключ добавляет прокси


KEYS = _keys()
_ki = [0]


def call(model, body, tries=4):
    """model может быть списком через запятую: каждая следующая — запасная."""
    models = model.split(",")
    for j, m in enumerate(models):
        try:
            return _call(m, body, tries)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if j == len(models) - 1:
                raise
            print(f"[gemini {m} недоступна — {models[j + 1]}]", flush=True)


def _call(model, body, tries):
    for i in range(tries * len(KEYS)):
        headers = {"Content-Type": "application/json"}
        k = KEYS[_ki[0] % len(KEYS)]
        if k:
            headers["x-goog-api-key"] = k
        try:
            req = urllib.request.Request(API + model + ":generateContent", json.dumps(body).encode(), headers)
            return json.load(urllib.request.urlopen(req, timeout=180))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if i == tries * len(KEYS) - 1:
                raise
            if getattr(e, "code", 0) == 429 and len(KEYS) > 1:
                _ki[0] += 1  # лимит ключа — следующий ключ
                if _ki[0] % len(KEYS):
                    continue
            # 429 на всех ключах — лимит в минуту: ждём дольше
            time.sleep((30 if getattr(e, "code", 0) == 429 else 5) * (i // len(KEYS) + 1))
            print(f"[gemini {model}: {e} — повтор]", flush=True)


def text_of(resp):
    return "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"]).strip()


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

Ответ — строго JSON без markdown:
{"say": "что ты говоришь вслух", "lang": "it" | "ru" | "mix", "error": "какую ошибку ты сделала нарочно, по-русски, или null"}"""


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
        resp = call(TEXT_MODEL, {"systemInstruction": {"parts": [{"text": STUDENT_SYSTEM}]},
                                 "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                 "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"}})
        raw = text_of(resp)
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            d = {"say": raw.strip("` \n"), "lang": "it", "error": None}
        self.dialog.append(("Анна", d["say"]))
        return d

    def speak(self, text):
        """Голос Анны: Gemini TTS, русский акцент начинающей, ошибки не исправлять. → (float32, 24000)"""
        style = ("Read aloud exactly as written, as a young Russian woman who has just started learning Italian: "
                 "strong Russian accent, a bit slow and unsure. Do NOT correct any mistakes")
        resp = call(TTS_MODEL, {"contents": [{"parts": [{"text": f"{style}: {text}"}]}],
                                "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.voice}}}}})
        pcm = base64.b64decode(resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768, 24000


# ---------------------------------------------------------------- судья
def _paolo_system():
    p = os.path.join(HERE, "..", "tools", "expert", "paolo_system.txt")
    return open(p).read() if os.path.exists(p) else "Ты — Паоло, опытный учитель итальянского."


TURN_Q = ("Это слепая проверка офлайн-учителя итальянского для нашей школы (работает без интернета). "
          "Ученица (A1, русская) сказала: «{said}»{err}. Прикреплён звук ответа учителя. Оцени как коллега: "
          "правильность итальянского, произношение и ударения, естественность голоса, и хорош ли это ответ учителя "
          "(по делу, коротко, заметил ли и исправил ли ошибку ученицы, не придумал ли ошибку, которой не было). "
          "Ответь строго JSON: {{\"score\": 1-5, \"caught_error\": true/false/null, \"comment\": \"1–2 фразы по-русски\"}}")


def judge_turn(said, intended_error, wav_bytes):
    err = f" (в реплике есть ошибка: {intended_error})" if intended_error else " (ошибки в реплике нет)"
    resp = call(JUDGE_MODEL, {"systemInstruction": {"parts": [{"text": _paolo_system()}]},
                              "contents": [{"role": "user", "parts": [
                                  {"text": TURN_Q.format(said=said, err=err)},
                                  {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav_bytes).decode()}}]}],
                              "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}})
    try:
        return json.loads(text_of(resp))
    except json.JSONDecodeError:
        return {"score": None, "caught_error": None, "comment": text_of(resp)[:300]}


LESSON_Q = ("Вот запись урока офлайн-учителя итальянского (без интернета) с ученицей A1. «Ученица сказала» — что она "
            "сказала на самом деле, «уши услышали» — что распознал компьютер, «Учитель» — ответ.\n\n{log}\n\n"
            "Оцени урок целиком как опытный коллега: ведёт ли по плану, замечает ли ошибки, не придумывает ли их, "
            "понятно ли ученице, живой ли разговор. Ответь строго JSON: {{\"score\": 1-5, \"good\": \"…\", "
            "\"bad\": \"…\", \"fix\": \"что изменить в инструкции учителя в первую очередь\"}}")


def judge_lesson(turns):
    log = "\n".join(f"Ученица сказала: {t['student_said']}\nУши услышали: {t['heard']}\nУчитель: {t['marked']}\n"
                    for t in turns)
    resp = call(JUDGE_MODEL, {"systemInstruction": {"parts": [{"text": _paolo_system()}]},
                              "contents": [{"role": "user", "parts": [{"text": LESSON_Q.format(log=log)}]}],
                              "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}})
    try:
        return json.loads(text_of(resp))
    except json.JSONDecodeError:
        return {"score": None, "comment": text_of(resp)[:500]}
