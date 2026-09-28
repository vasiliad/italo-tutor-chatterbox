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
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "https://api.kaggle.com/v1"
ROOT = Path(__file__).resolve().parent.parent
SLUG = "italo-tutor-chatterbox-eval"
STATE = ROOT / "kaggle_output" / "kernel.json"   # сюда запоминаем ref после push


def call(service, method, body):
    headers = {"Content-Type": "application/json"}
    if tok := os.environ.get("KAGGLE_API_TOKEN"):
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.post(f"{API}/{service}/{method}", json=body, headers=headers, timeout=120)
    if r.status_code != 200:
        sys.exit(f"{method}: HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def kernel_ref():
    if STATE.exists():
        return json.loads(STATE.read_text())["ref"]
    if user := os.environ.get("KAGGLE_USERNAME"):
        return f"{user}/{SLUG}"
    sys.exit("Неизвестен владелец ноутбука: сначала push или задайте KAGGLE_USERNAME")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["quota", "push", "status", "output"])
    ap.add_argument("--accelerator", default="NvidiaTeslaT4")
    a = ap.parse_args()

    if a.cmd == "quota":
        print(json.dumps(call("kernels.KernelsApiService", "GetAcceleratorQuotaStatistics", {}), indent=1))

    elif a.cmd == "push":
        user = os.environ.get("KAGGLE_USERNAME")
        body = {
            "newTitle": SLUG,   # без slug Kaggle сам создаёт/обновляет ноутбук текущего пользователя
            "text": (ROOT / "chatterbox_eval.ipynb").read_text(),
            "language": "python",
            "kernelType": "notebook",
            "isPrivate": True,
            "enableGpu": True,
            "enableInternet": True,
            "machineShape": a.accelerator,
        }
        if user:
            body["slug"] = f"{user}/{SLUG}"
        res = call("kernels.KernelsApiService", "SaveKernel", body)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        if res.get("error"):
            sys.exit(1)
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps({"ref": res["ref"].strip("/"), "url": res.get("url"),
                                     "version": res.get("versionNumber")}))

    elif a.cmd == "status":
        user, slug = kernel_ref().split("/")[-2:]
        print(json.dumps(call("kernels.KernelsApiService", "GetKernelSessionStatus",
                              {"userName": user, "kernelSlug": slug}), indent=1, ensure_ascii=False))

    elif a.cmd == "output":
        user, slug = kernel_ref().split("/")[-2:]
        out = ROOT / "kaggle_output"
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
