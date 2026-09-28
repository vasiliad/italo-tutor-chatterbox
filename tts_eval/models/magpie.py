"""NVIDIA MagpieTTS Multilingual 357M (v2607): только it из наших; итальянский читается побайтно (byt5) —
фонемного ввода нет, поэтому только plain/accent. Голоса английские (Sofia=4).
pip install "nemo_toolkit[tts] @ git+https://github.com/NVIDIA-NeMo/Speech.git@cf724ac337d1ebc7d0dda1e23fb80916f52927a5" kaldialign
(PyPI nemo 3.0.0 молча берёт английский токенизатор для it.)
"""
SPEAKER = 4


def load(device):
    from nemo.collections.tts.models import MagpieTTSModel
    return MagpieTTSModel.from_pretrained("nvidia/magpie_tts_multilingual_357m").to(device).eval()


def variants(item):
    return ["plain", "accent"] if item["lang"] == "it" else []


def synth(m, item, v):
    import torch
    with torch.no_grad():
        audio, n = m.do_tts(item["inputs"][v], language="it", apply_TN=False, speaker_index=SPEAKER)
    return audio[0, :n[0]].float().cpu().numpy(), m.output_sample_rate
