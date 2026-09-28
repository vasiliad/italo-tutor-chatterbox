import json, sys
cells = []
def md(s): cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})
md(r"""
# Экспертиза записей Chatterbox на слух: Паоло (it, ru) и Хава (he) — gemini-3.1-flash-live-preview (основная) и gemini-3.8-live (запасная)

Вход — последний прогон из `results/` репозитория (или вывод `italo-tutor-chatterbox-eval`, подключённый как Input). Ключ Gemini — Kaggle Secret `GEMINI_API_KEY`
(Add-ons → Secrets, галочка для этого ноутбука). GPU не нужен, Internet = On.
Вопросы слепые: эксперт выбирает из вариантов в случайном порядке, что прозвучало; ответ сравнивается с задуманным.
""")
code(r"""
!pip install -q websockets soundfile
!rm -rf /kaggle/working/task && git clone -q --depth 1 https://github.com/vasiliad/italo-tutor-chatterbox /kaggle/working/task
""")
code(r"""
import os, glob, shutil, subprocess, sys
from kaggle_secrets import UserSecretsClient
# Ключи: секреты GEMINI_API_KEY, GEMINI_API_KEY_2 … _9 (каждый отдельным секретом с галочкой)
keys, sc = [], UserSecretsClient()
for name in ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 10)]:
    try:
        keys.append(sc.get_secret(name).strip())
    except Exception:
        pass
# Запуски через API секретов не видят — тогда ключи из приватного Dataset (key-google, подключается
# скриптом kaggle_api.py): ищем ключи Gemini по формату в любом .txt, оформление файла не важно
import re
if not keys:
    for f in glob.glob("/kaggle/input/**/*.txt", recursive=True):
        found = [k for k in re.findall(r"[A-Za-z0-9_.\-]{30,}", open(f).read()) if k not in keys]
        print(os.path.basename(f), "— ключей:", len(found), "длины:", [len(k) for k in found])
        keys += found
print("ключей:", len(keys))
assert keys, "Нет ключей: ни секрета GEMINI_API_KEY, ни .txt с ключами в подключённом Dataset"
os.makedirs(os.path.expanduser("~/key"), exist_ok=True)
open(os.path.expanduser("~/key/key"), "w").write("\n".join(keys))

# Записи: подключённый Input или последний прогон в репозитории (results/<дата>_<версия>/)
src = glob.glob("/kaggle/input/**/results.csv", recursive=True) or \
      sorted(glob.glob("/kaggle/working/task/results/*/results.csv"))[-1:]
print("найдено:", src)
assert src, "Нет записей: ни Input, ни results/ в репозитории"
ROOT = "/kaggle/working/chatterbox_eval"
shutil.copytree(os.path.dirname(src[0]), ROOT, dirs_exist_ok=True)
""")
code(r"""
# Сначала проверка связи: 3 задания
!cd /kaggle/working/task/tools/expert && python3 expert_listen.py --root /kaggle/working/chatterbox_eval --limit 3
""")
code(r"""
# Полная экспертиза: не чаще 20 вопросов в минуту на ключ (ключи из разных проектов — лимиты у каждого свои), по приоритету.
# Продолжает с места остановки: ответы прошлых запусков берутся из репозитория (expert_results.csv).
!cd /kaggle/working/task/tools/expert && python3 expert_listen.py --root /kaggle/working/chatterbox_eval --per-min 20 --per-key
""")
code(r"""
# Те же вопросы запасной модели gemini-3.8-live (на случай отключения 3.1-preview) — отдельный файл
!cd /kaggle/working/task/tools/expert && python3 expert_listen.py --root /kaggle/working/chatterbox_eval --per-min 20 --per-key --model models/gemini-3.8-live
""")

code(r"""
import pandas as pd
out = "/kaggle/working/expert_out"
os.makedirs(out, exist_ok=True)
for f in glob.glob("/kaggle/working/chatterbox_eval/expert_*"):
    shutil.copy(f, out)
    if f.endswith(".md"):
        print(open(f).read())
shutil.rmtree("/kaggle/working/chatterbox_eval"); shutil.rmtree("/kaggle/working/task", ignore_errors=True)
os.remove(os.path.expanduser("~/key/key"))
""")
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
for c in nb["cells"]:
    c["source"] = [l + "\n" for l in c["source"].split("\n")]; c["source"][-1] = c["source"][-1].rstrip("\n")
json.dump(nb, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
