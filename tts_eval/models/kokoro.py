"""Kokoro-82M (Apache-2.0), контроль: фонемы выполняет буквально. Только итальянский (if_sara).
pip install kokoro soundfile  (+ espeak-ng в системе или espeakng_loader из зависимостей)
"""
from models.common import affricates

VOICE = "if_sara"


def load(device):
    from kokoro import KPipeline
    return KPipeline(lang_code="i", repo_id="hexgrad/Kokoro-82M", device=device)


def variants(item):
    if item["lang"] != "it":
        return []
    return [v for v in ("plain", "accent", "ipa", "ipa_len") if v in item["inputs"]]


def synth(p, item, v):
    import numpy as np
    text = item["inputs"][v]
    if v.startswith("ipa"):
        parts = [r.audio.numpy() for r in p.generate_from_tokens(affricates(text), voice=VOICE)]
    else:
        parts = [r.audio.numpy() for r in p(text, voice=VOICE)]
    return np.concatenate(parts), 24000
