#!/usr/bin/env python3
"""Даём Пауло послушать аудиозаписи (WAV 24kHz mono) и задать вопрос.

Записи склеиваются с паузами, пересэмплируются в 16kHz (формат входа
Live API) и отправляются как одна реплика, затем текстовый вопрос.

  python3 tools/paolo_listen.py --question-file q.txt a.wav b.wav c.wav
"""
import argparse
import asyncio
import base64
import json
import os
import struct
import sys
import wave

import websockets

sys.path.insert(0, os.path.dirname(__file__))
from paolo import MODEL, URL, load_keys  # noqa: E402


def read_pcm16(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1
        rate = w.getframerate()
        data = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(data) // 2}h", data)
    return list(samples), rate


def resample(samples, src, dst):
    if src == dst:
        return samples
    n = int(len(samples) * dst / src)
    out = []
    for i in range(n):
        x = i * src / dst
        j = int(x)
        f = x - j
        a = samples[j]
        b = samples[j + 1] if j + 1 < len(samples) else a
        out.append(int(a + (b - a) * f))
    return out


async def listen(key, system, voice, audio_16k, question, timeout, model=MODEL):
    # key=None: ключ подставляет прокси окружения (API credential), сами заголовок не шлём
    headers = {"x-goog-api-key": key} if key else {}
    async with websockets.connect(URL, additional_headers=headers,
                                  max_size=None, open_timeout=30) as ws:
        setup = {"setup": {
            "model": model,
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}}},
            },
            "outputAudioTranscription": {},
            "realtimeInputConfig": {
                "automaticActivityDetection": {"disabled": True}},
        }}
        if system:
            setup["setup"]["systemInstruction"] = {"parts": [{"text": system}]}
        await ws.send(json.dumps(setup))
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout))
        if "setupComplete" not in first:
            raise RuntimeError(f"setup failed: {first}")

        pcm = struct.pack(f"<{len(audio_16k)}h", *audio_16k)
        await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
        await ws.send(json.dumps({"realtimeInput": {"text": question}}))
        chunk = 16000 * 2  # 1 секунда
        for i in range(0, len(pcm), chunk):
            await ws.send(json.dumps({"realtimeInput": {"audio": {
                "mimeType": "audio/pcm;rate=16000",
                "data": base64.b64encode(pcm[i:i + chunk]).decode()}}}))
        await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))

        transcript = []
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout))
            sc = msg.get("serverContent")
            if not sc:
                if "error" in msg or "goAway" in msg:
                    raise RuntimeError(str(msg))
                continue
            tr = sc.get("outputTranscription")
            if tr and tr.get("text"):
                transcript.append(tr["text"])
            if sc.get("turnComplete"):
                break
        return "".join(transcript)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wavs", nargs="+")
    ap.add_argument("--question-file", required=True)
    ap.add_argument("--system-file")
    ap.add_argument("--voice", default="Algenib")
    ap.add_argument("--keys", default="~/key/key")
    ap.add_argument("--gap", type=float, default=1.5)
    ap.add_argument("--timeout", type=float, default=120)
    a = ap.parse_args()

    audio = []
    for p in a.wavs:
        s, rate = read_pcm16(p)
        audio += resample(s, rate, 16000) + [0] * int(16000 * a.gap)
    question = open(a.question_file).read()
    system = open(a.system_file).read() if a.system_file else None

    for i, key in enumerate(load_keys(a.keys), 1):
        try:
            print(await listen(key, system, a.voice, audio, question, a.timeout))
            print(f"[key#{i} ok]", file=sys.stderr)
            return
        except Exception as e:
            print(f"[key#{i} failed: {str(e)[:300]}]", file=sys.stderr)
    sys.exit("все ключи не сработали")


if __name__ == "__main__":
    asyncio.run(main())
