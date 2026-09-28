"""Piper (piper1-gpl, ONNX, CPU), контроль: выполняет [[ фонемы ]]. it — paola, ru — irina.
pip install piper-tts ; голоса: python -m piper.download_voices it_IT-paola-medium ru_RU-irina-medium
"""
import os

from models.common import with_word_ipa

VOICES = {"it": "it_IT-paola-medium", "ru": "ru_RU-irina-medium"}
VOICE_DIR = os.environ.get("PIPER_VOICES", ".")


def load(device):
    from piper import PiperVoice
    return {lang: PiperVoice.load(os.path.join(VOICE_DIR, f"{v}.onnx")) for lang, v in VOICES.items()}


def variants(item):
    if item["lang"] == "it":
        return [v for v in ("plain", "accent", "ipa", "ipa_len") if v in item["inputs"]]
    if item["lang"] == "ru":
        return [v for v in ("plain", "accent") if v in item["inputs"]] + (["ipa"] if "ipa_word" in item["inputs"] else [])
    return []


def synth(voices, item, v):
    import numpy as np
    voice = voices[item["lang"]]
    if item["lang"] == "ru" and v == "ipa":
        text = with_word_ipa(item, lambda ipa: f"[[ {ipa} ]]")
    elif v.startswith("ipa"):
        text = f"[[ {item['inputs'][v]} ]]"
    else:
        text = item["inputs"][v]
    chunks = list(voice.synthesize(text))
    y = np.concatenate([c.audio_float_array for c in chunks])
    return y, chunks[0].sample_rate
