"""MOSS-TTS (OpenMOSS, Apache-2.0): it/ru/he, клон, IPA внутри текста в /…/.
Версия — переменная MOSS_REPO:
  OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5  (4B + кодек 2B, 48 кГц; he только здесь)
  OpenMOSS-Team/MOSS-TTS-Local-Transformer       (v1.0, бэкбон 1.7B, 24 кГц — кандидат для Mac 16 ГБ)
pip install "transformers==5.0.0" accelerate torchcodec einops librosa soundfile  (код модели — trust_remote_code)
T4 без bf16: основная модель в fp16 (MOSS_DTYPE=fp32 — если NaN), кодек — на второй GPU, если она есть.
Варианты: plain, accent, ipa (вся фраза в /…/), ipa_word (только проверяемое слово в /…/), ipa_len*, clone.
"""
import glob
import os

from models.common import LANG_NAME, with_word_ipa

REPO = os.environ.get("MOSS_REPO", "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5")
V15 = REPO.endswith("v1.5")
GEN = (dict(audio_temperature=1.7, audio_top_p=0.8, audio_top_k=25, audio_repetition_penalty=1.0) if V15 else
       dict(audio_temperature=1.0, audio_top_p=0.95, audio_top_k=50, audio_repetition_penalty=1.1))
REF = os.environ.get("CLONE_REF")  # 10 с голоса для клона


def load(device):
    import torch
    from transformers import AutoModel, AutoProcessor
    torch.backends.cuda.enable_cudnn_sdp(False)
    dtype = torch.float32 if os.environ.get("MOSS_DTYPE") == "fp32" else torch.float16
    proc = AutoProcessor.from_pretrained(REPO, trust_remote_code=True)
    codec_dev = "cuda:1" if torch.cuda.device_count() > 1 else device
    if os.environ.get("MOSS_CODEC_CPU"):
        codec_dev = "cpu"
    proc.audio_tokenizer = proc.audio_tokenizer.to(codec_dev)
    model = AutoModel.from_pretrained(REPO, trust_remote_code=True, attn_implementation="sdpa",
                                      torch_dtype=dtype).to(device).eval()
    print("MOSS", REPO, dtype, "кодек на", codec_dev, flush=True)
    return dict(proc=proc, model=model, device=device)


def variants(item):
    lang, inp = item["lang"], item["inputs"]
    if lang == "he" and not V15:
        return []
    vs = [v for v in ("plain", "accent", "niqqud", "ipa", "ipa_len") if v in inp and not (lang == "ru" and v == "ipa")]
    vs += [v for v in ("ipa_word", "ipa_len_word") if v in inp]
    if REF and item["section"] in ("it_a1", "ru"):
        vs.append("clone")
    return vs


def text_for(item, v):
    inp = item["inputs"]
    if v in ("ipa", "ipa_len"):
        return f"/{inp[v]}/"
    if v in ("ipa_word", "ipa_len_word"):
        return with_word_ipa(item, lambda ipa: f"/{ipa}/", key=v)
    if v == "clone":
        return inp["plain"]
    return inp[v]


def synth(m, item, v):
    import torch
    proc, model, dev = m["proc"], m["model"], m["device"]
    kw = dict(text=text_for(item, v), language=LANG_NAME[item["lang"]])
    if v == "clone":
        kw["reference"] = [REF]
    batch = proc([[proc.build_user_message(**kw)]], mode="generation")
    with torch.no_grad():
        out = model.generate(input_ids=batch["input_ids"].to(dev), attention_mask=batch["attention_mask"].to(dev),
                             max_new_tokens=1024, do_sample=True, **GEN)
    audio = list(proc.decode(out))[0].audio_codes_list[0].detach().float().cpu()
    if audio.ndim == 2:  # v1.5: стерео [2, N] → моно
        audio = audio.mean(0) if audio.shape[0] == 2 else audio.mean(1)
    return audio.numpy(), proc.model_config.sampling_rate
