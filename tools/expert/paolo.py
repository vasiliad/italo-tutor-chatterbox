#!/usr/bin/env python3
"""Разговор с Пауло через gemini-3.1-flash-live-preview (Live API, WebSocket).

Ключи читаются из файла (по умолчанию ~/key/key, по одному на строку/через
пробел), перебираются по очереди при ошибке. Ответ Пауло: текст
(транскрипция его речи) печатается, аудио сохраняется в WAV.

Пример:
  python3 tools/paolo.py --voice Puck --out /tmp/paolo.wav "Ciao Paolo!"
  python3 tools/paolo.py --system-file prompt.txt --message-file msg.txt
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import wave

import websockets

MODEL = "models/gemini-3.1-flash-live-preview"
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "docs", "paolo", "memory.md")
URL = ("wss://generativelanguage.googleapis.com/ws/"
       "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")


def load_keys(path):
    """Ключи из файла. Нет файла — [None]: ключ добавит прокси облачного окружения."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return [None]
    with open(path) as f:
        return [k for k in f.read().split() if k]


def with_memory(system, memory_path):
    """Добавляет к инструкции Пауло его тетрадь (память между разговорами)."""
    path = os.path.expanduser(memory_path) if memory_path else None
    if not path or not os.path.exists(path):
        return system
    return (system or "") + "\n\n=== ТЕТРАДЬ ПАОЛО (твоя память о прошлых разговорах) ===\n" + open(path).read()


async def talk(key, voice, system, message, out_wav, timeout):
    headers = {"x-goog-api-key": key} if key else {}
    async with websockets.connect(URL, additional_headers=headers,
                                  max_size=None, open_timeout=30) as ws:
        setup = {
            "setup": {
                "model": MODEL,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}}},
                },
                "outputAudioTranscription": {},
            }
        }
        if system:
            setup["setup"]["systemInstruction"] = {"parts": [{"text": system}]}
        await ws.send(json.dumps(setup))

        first = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if "setupComplete" not in first:
            raise RuntimeError(f"setup failed: {first}")

        await ws.send(json.dumps({"realtimeInput": {"text": message}}))

        audio = bytearray()
        transcript = []
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout)
            msg = json.loads(raw)
            sc = msg.get("serverContent")
            if not sc:
                if "goAway" in msg or "error" in msg:
                    raise RuntimeError(str(msg))
                continue
            for part in (sc.get("modelTurn") or {}).get("parts", []):
                inline = part.get("inlineData")
                if inline and inline.get("mimeType", "").startswith("audio/"):
                    audio += base64.b64decode(inline["data"])
            tr = sc.get("outputTranscription")
            if tr and tr.get("text"):
                transcript.append(tr["text"])
            if sc.get("turnComplete"):
                break

    if out_wav and audio:
        with wave.open(out_wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(bytes(audio))
    return "".join(transcript), len(audio)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="?")
    ap.add_argument("--message-file")
    ap.add_argument("--system-file")
    ap.add_argument("--voice", default="Algenib")
    ap.add_argument("--out")
    ap.add_argument("--keys", default="~/key/key")
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--memory", default=MEMORY_FILE, help="тетрадь Пауло; пусто — без памяти")
    a = ap.parse_args()

    message = open(a.message_file).read() if a.message_file else a.message
    system = with_memory(open(a.system_file).read() if a.system_file else None, a.memory)
    if not message:
        sys.exit("нужно сообщение")

    last_err = None
    for i, key in enumerate(load_keys(a.keys), 1):
        try:
            text, n = await talk(key, a.voice, system, message, a.out, a.timeout)
            print(f"[key#{i} ok, audio {n / 48000:.1f}s]", file=sys.stderr)
            print(text)
            return
        except Exception as e:  # пробуем следующий ключ
            last_err = e
            print(f"[key#{i} failed: {str(e)[:300]}]", file=sys.stderr)
    sys.exit(f"все ключи не сработали: {last_err}")


if __name__ == "__main__":
    asyncio.run(main())
