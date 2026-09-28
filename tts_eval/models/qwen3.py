"""Qwen3-TTS (Apache-2.0): it/ru, без IPA и без иврита. QWEN_MODE=voice — готовый голос (CustomVoice),
QWEN_MODE=clone — клон по образцу (Base, x_vector_only без расшифровки образца).
pip install qwen-tts  (тянет transformers==4.57.3). T4: fp32 (fp16 у Qwen3 рискует переполнением).
"""
import os

from models.common import LANG_NAME

MODE = os.environ.get("QWEN_MODE", "voice")
SIZE = os.environ.get("QWEN_SIZE", "1.7B")
SPEAKER = os.environ.get("QWEN_SPEAKER", "Ryan")
REF = os.environ.get("CLONE_REF")


def load(device):
    import torch
    from qwen_tts import Qwen3TTSModel
    repo = f"Qwen/Qwen3-TTS-12Hz-{SIZE}-{'CustomVoice' if MODE == 'voice' else 'Base'}"
    print("Qwen3", repo, flush=True)
    return Qwen3TTSModel.from_pretrained(repo, device_map=device, dtype=torch.float32, attn_implementation="sdpa")


def variants(item):
    if item["lang"] not in ("it", "ru") or (MODE == "clone" and not REF):
        return []
    if MODE == "clone" and item["section"] not in ("it_a1", "ru", "it_context"):
        return []
    return [v for v in ("plain", "accent") if v in item["inputs"]]


def synth(m, item, v):
    text, lang = item["inputs"][v], LANG_NAME[item["lang"]]
    if MODE == "voice":
        wavs, sr = m.generate_custom_voice(text=text, language=lang, speaker=SPEAKER)
    else:
        wavs, sr = m.generate_voice_clone(text=text, language=lang, ref_audio=REF, x_vector_only_mode=True)
    return wavs[0], sr
