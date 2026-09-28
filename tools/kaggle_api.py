#!/usr/bin/env python3
"""Запуск chatterbox_eval.ipynb на Kaggle через API — без kaggle CLI.

В облачном окружении Claude ключ Kaggle хранится как API credential: прокси сам
добавляет заголовок Authorization к запросам на *.kaggle.com, а процесс ключа не видит.
kaggle CLI так работать не может: он проверяет токен, отправляя его в теле запроса.
Поэтому зовём REST API напрямую. Локально можно задать KAGGLE_API_TOKEN — тогда
заголовок добавит сам скрипт.

  python3 tools/kaggle_api.py quota
  python3 tools/kaggle_api.py push [--accelerator NvidiaTeslaT4]
  python3 tools/kaggle_api.py status
  python3 tools/kaggle_api.py output        # в ./kaggle_output/
  --task expert — второй ноутбук: экспертиза на слух (Паоло/Хава, Gemini Live), вход — вывод eval
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "https://api.kaggle.com/v1"
ROOT = Path(__file__).resolve().parent.parent
TASKS = {  # задача -> (ноутбук, slug на Kaggle, GPU, входы — другие ноутбуки)
    "eval": ("chatterbox_eval.ipynb", "italo-tutor-chatterbox-eval", True, []),
    "expert": ("expert_review.ipynb", "italo-tutor-chatterbox-expert", False, ["italo-tutor-chatterbox-eval"]),
}
TASK = "eval"


def state_file():
    return ROOT / "kaggle_output" / ("kernel.json" if TASK == "eval" else f"kernel_{TASK}.json")


def call(service, method, body):
    headers = {"Content-Type": "application/json"}
    if tok := os.environ.get("KAGGLE_API_TOKEN"):
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.post(f"{API}/{service}/{method}", json=body, headers=headers, timeout=120)
    if r.status_code != 200:
        sys.exit(f"{method}: HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def kernel_ref():
    if state_file().exists():
        return json.loads(state_file().read_text())["ref"]
    eval_state = ROOT / "kaggle_output" / "kernel.json"
    user = os.environ.get("KAGGLE_USERNAME") or (
        json.loads(eval_state.read_text())["ref"].split("/")[-2] if eval_state.exists() else None)
    if user:
        return f"{user}/{TASKS[TASK][1]}"
    sys.exit("Неизвестен владелец ноутбука: сначала push или задайте KAGGLE_USERNAME")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["quota", "push", "status", "output"])
    ap.add_argument("--accelerator", default="NvidiaTeslaT4")
    ap.add_argument("--task", choices=list(TASKS), default="eval")
    a = ap.parse_args()
    global TASK
    TASK = a.task
    nb_file, slug, gpu, sources = TASKS[TASK]

    if a.cmd == "quota":
        print(json.dumps(call("kernels.KernelsApiService", "GetAcceleratorQuotaStatistics", {}), indent=1))

    elif a.cmd == "push":
        user = os.environ.get("KAGGLE_USERNAME")
        try:
            user = user or kernel_ref().split("/")[-2]   # логин из прошлого push
        except SystemExit:
            pass
        body = {
            "newTitle": slug,   # без slug Kaggle сам создаёт/обновляет ноутбук текущего пользователя
            "text": (ROOT / nb_file).read_text(),
            "language": "python",
            "kernelType": "notebook",
            "isPrivate": True,
            "enableGpu": gpu,
            "enableInternet": True,
        }
        if gpu:
            body["machineShape"] = a.accelerator
        if user:
            body["slug"] = f"{user}/{slug}"
            body["kernelDataSources"] = [f"{user}/{k}" for k in sources]
        res = call("kernels.KernelsApiService", "SaveKernel", body)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        if res.get("error"):
            sys.exit(1)
        state_file().parent.mkdir(exist_ok=True)
        state_file().write_text(json.dumps({"ref": res["ref"].strip("/"), "url": res.get("url"),
                                     "version": res.get("versionNumber")}))

    elif a.cmd == "status":
        user, slug = kernel_ref().split("/")[-2:]
        print(json.dumps(call("kernels.KernelsApiService", "GetKernelSessionStatus",
                              {"userName": user, "kernelSlug": slug}), indent=1, ensure_ascii=False))

    elif a.cmd == "output":
        user, slug = kernel_ref().split("/")[-2:]
        out = ROOT / "kaggle_output" / ("" if TASK == "eval" else TASK)
        out.mkdir(exist_ok=True)
        token = None
        while True:
            body = {"userName": user, "kernelSlug": slug, "pageSize": 100}
            if token:
                body["pageToken"] = token
            res = call("kernels.KernelsApiService", "ListKernelSessionOutput", body)
            if res.get("log"):
                (out / "log.txt").write_text(res["log"])
            for f in res.get("files", []):
                dst = out / f["fileName"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                with requests.get(f["url"], stream=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(dst, "wb") as fh:
                        for chunk in r.iter_content(1 << 20):
                            fh.write(chunk)
                print(f"{dst.relative_to(ROOT)}  {dst.stat().st_size // 1024} КБ")
            token = res.get("nextPageToken")
            if not token:
                break


if __name__ == "__main__":
    main()
