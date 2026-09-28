#!/usr/bin/env python3
"""Собирает tts_eval.ipynb — сравнение локальных TTS на Kaggle (GPU T4, интернет).
Каждая модель ставится в свой venv (--system-site-packages: torch берём у Kaggle), падение одной не рушит остальные.
  python3 tools/make_tts_notebook.py && python3 tools/kaggle_api.py push --task tts
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MD_INTRO = """# Локальные TTS для офлайн-учителя: MOSS-TTS, Qwen3-TTS, MagpieTTS, контроль Kokoro и Piper

Задача: найти модель, которая без интернета **правильно ставит ударение и долготу согласных** в итальянском
(и по возможности говорит по-русски и на иврите). Один набор фраз `tts_eval/testset.json` (68 пунктов) —
в трёх видах ввода: обычный текст, текст с ударениями, фонемы IPA (вся фраза или только проверяемое слово).
Результат: `out/<модель>/` — WAV, meta.csv (скорость), asr.csv (Whisper, CER), `out/summary.md`, архивы `wav_<модель>.zip`.
Код: [vasiliad/italo-tutor-chatterbox](https://github.com/vasiliad/italo-tutor-chatterbox) `tts_eval/`."""

SETUP = r'''import os, subprocess, sys, time, glob, shutil
t0 = time.time()
subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv", shell=True)
subprocess.run("rm -rf /kaggle/working/task && git clone -q --depth 1 https://github.com/vasiliad/italo-tutor-chatterbox /kaggle/working/task", shell=True, check=True)
subprocess.run("apt-get -qq -y install espeak-ng > /dev/null 2>&1; espeak-ng --version", shell=True)
TASK = "/kaggle/working/task"; OUT = "/kaggle/working/out"; ENVS = "/tmp/envs"
os.makedirs(OUT, exist_ok=True); os.makedirs(ENVS, exist_ok=True)
os.environ["HF_HOME"] = "/tmp/hf"
subprocess.run("pip install -q uv", shell=True, check=True)  # в venv на Kaggle нет ensurepip → uv venv
# ставим pip'ом Kaggle (--python): он видит системные пакеты; uv их не видит и тянет свой torch (ломает torchvision)
subprocess.run("pip freeze | grep -E '^(torch|torchvision|torchaudio)==' > /tmp/torch_pin.txt; cat /tmp/torch_pin.txt", shell=True)
# образец голоса для клона: 10 с из refs/paolo_offline_keys.wav
import soundfile as sf
y, sr = sf.read(f"{TASK}/refs/paolo_offline_keys.wav")
sf.write("/tmp/ref10.wav", y[: sr * 10], sr)
os.environ["CLONE_REF"] = "/tmp/ref10.wav"
STATUS = {}

def sh(cmd, env=None, timeout=None):
    """Команда с потоковым выводом (хвост в лог), код возврата."""
    p = subprocess.Popen(cmd, shell=True, env={**os.environ, **(env or {})}, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, cwd=TASK)
    t = time.time()
    try:
        for line in p.stdout:
            if "Warning" not in line and "warn(" not in line:
                print(line, end="", flush=True)
            if timeout and time.time() - t > timeout:
                p.kill(); print(f"!!! таймаут {timeout} с", flush=True); return -9
    finally:
        p.wait()
    return p.returncode

def model(name, pip, env=None, pre="", timeout=5400):
    """venv модели → установка → run_model.py; итог в STATUS."""
    t = time.time()
    venv = f"{ENVS}/{name}"
    py = f"{venv}/bin/python"
    rc = sh(f"uv venv -q --system-site-packages {venv} && python3 -m pip --python {py} install -q -c /tmp/torch_pin.txt {pip} 2>&1 | grep -v -E 'WARN|notice' | tail -15", timeout=1800)
    if rc == 0 and pre:
        rc = sh(pre.replace("{py}", py), env=env)
    if rc == 0:
        rc = sh(f"{py} tts_eval/run_model.py {name.split('@')[0]} --out {OUT}", env=env, timeout=timeout)
    if "@" in name:  # несколько прогонов одного адаптера: out/<адаптер> → out/<имя>
        src, dst = f"{OUT}/{name.split('@')[0]}", f"{OUT}/{name.replace('@', '_')}"
        if os.path.exists(src):
            shutil.rmtree(dst, ignore_errors=True); os.rename(src, dst)
    STATUS[name] = dict(rc=rc, min=round((time.time() - t) / 60, 1))
    print(f"=== {name}: код {rc}, {STATUS[name]['min']} мин, всего {round((time.time() - t0) / 60)} мин", flush=True)
    shutil.rmtree("/tmp/hf/hub", ignore_errors=True)  # место на диске
'''

CELLS = [
    ("md", "## Контроль: Piper (ONNX, CPU) и Kokoro-82M — фонемы выполняют буквально"),
    ("code", 'model("piper", "piper-tts soundfile", env={"PIPER_VOICES": "/tmp/piper"},\n'
             '      pre="{py} -m piper.download_voices --download-dir /tmp/piper it_IT-paola-medium ru_RU-irina-medium")'),
    ("code", 'model("kokoro", "\\"kokoro>=0.9.4\\" soundfile pip")'),
    ("md", "## Qwen3-TTS 1.7B: готовый голос и клон по образцу (без IPA)"),
    ("code", 'QW = "qwen-tts soundfile"\n'
             'model("qwen3@voice", QW, env={"QWEN_MODE": "voice"})\n'
             'model("qwen3@clone", QW, env={"QWEN_MODE": "clone"})'),
    ("md", "## MOSS-TTS: v1.0 (1.7B — размер для Mac 16 ГБ) и v1.5 (4B), IPA в `/…/`"),
    ("code", 'MOSS = "\\"transformers==5.0.0\\" accelerate torchcodec einops librosa soundfile"\n'
             'model("moss@v10", MOSS, env={"MOSS_REPO": "OpenMOSS-Team/MOSS-TTS-Local-Transformer"})\n'
             'model("moss@v15", MOSS, env={"MOSS_REPO": "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5"})'),
    ("md", "## MagpieTTS Multilingual 357M (NeMo main): только итальянский, без фонемного ввода"),
    ("code", 'model("magpie", "\\"nemo_toolkit[tts] @ git+https://github.com/NVIDIA-NeMo/Speech.git@cf724ac337d1ebc7d0dda1e23fb80916f52927a5\\" kaldialign soundfile", timeout=3600)'),
    ("md", "## Whisper: разборчивость (CER) и сводка"),
    ("code", 'model_rc = sh(f"uv venv -q --system-site-packages {ENVS}/asr && python3 -m pip --python {ENVS}/asr/bin/python install -q -c /tmp/torch_pin.txt \\"transformers>=4.57,<5\\" jiwer librosa && {ENVS}/asr/bin/python tts_eval/asr.py {OUT}")\n'
             'sh(f"python3 tts_eval/report.py {OUT}")\n'
             'print(STATUS)'),
    ("code", 'import json\n'
             'json.dump(STATUS, open(f"{OUT}/status.json", "w"), indent=1)\n'
             'for d in sorted(glob.glob(f"{OUT}/*/")):\n'
             '    m = os.path.basename(d.rstrip("/"))\n'
             '    sh(f"cd {d} && zip -q -r /kaggle/working/wav_{m}.zip *.wav && rm -f *.wav")\n'
             'shutil.rmtree(TASK, ignore_errors=True)  # клон репозитория не нужен в выводе\n'
             'print(subprocess.run("du -sh /kaggle/working/*", shell=True, capture_output=True, text=True).stdout)'),
]


def cell(kind, src):
    c = {"cell_type": "markdown" if kind == "md" else "code", "metadata": {}, "source": src.splitlines(True)}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


nb = {"cells": [cell("md", MD_INTRO), cell("code", SETUP)] + [cell(k, s) for k, s in CELLS],
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}
(ROOT / "tts_eval.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1))
print("tts_eval.ipynb:", len(nb["cells"]), "ячеек")
