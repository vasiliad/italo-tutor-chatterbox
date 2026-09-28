#!/usr/bin/env python3
"""Слепая экспертиза записей Chatterbox на слух: Паоло (итальянский, русский) и Хава (иврит)
на gemini-3.1-flash-live-preview.

Эксперт слышит одну запись и выбирает из вариантов (порядок перемешан), что прозвучало:
какое ударение, какое слово, одна или две согласные. Что мы хотели сказать, он не знает.
Для обычных фраз — оценка произношения 1–5. Ответ сравнивается с задуманным.

  python3 tools/expert_listen.py --root ../italo-tutor-chatterbox/kaggle_output/chatterbox_eval \
      [--only it_context,he_context] [--limit 5] [--jobs 3]

--root — папка с results.csv и wav/ из ноутбука Kaggle. Итог: expert_results.csv и expert_summary.md там же.
"""
import argparse
import asyncio
import csv
import os
import random
import re
import sys
import unicodedata
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from paolo import load_keys, with_memory  # noqa: E402
from paolo_listen import listen  # noqa: E402

HERE = os.path.dirname(__file__)
EXPERTS = {
    "paolo": dict(system=os.path.join(HERE, "paolo_system.txt"), voice="Algenib",
                  memory=next((p for p in [os.path.join(HERE, "..", "docs", "paolo", "memory.md"),
                                           os.path.join(HERE, "paolo_memory.md")] if os.path.exists(p)), None)),
    "hava": dict(system=os.path.join(HERE, "hava_system.txt"), voice="Aoede", memory=None),
}
INTRO = ("Это слепая проверка синтезатора речи для нашей школы. Ты услышишь одну запись. "
         "Суди только по звуку, не по тому, как «должно быть». ")
FORMAT_CHOICE = ("Ответь строго так: «Ответ: <номер варианта>», потом одной короткой фразой — почему. "
                 "Если не можешь различить — скажи «Ответ: ноль».")
FORMAT_RATE = ("Ответь строго так: «Оценка: <число от 1 до 5>», где 5 — как у носителя, 1 — непонятно; "
               "потом коротко перечисли ошибки произношения (ударения, звуки, акцент), если есть.")

def plain(s):
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", s)
                                                if unicodedata.category(c) != "Mn"))


# --- итальянский ------------------------------------------------------------------------------
IT_WRONG = {  # правильное ударение -> типичная ошибка (или второе слово омографа)
    "telèfonano": "telefònano", "parliàmo": "pàrliamo", "desìderano": "desidèrano",
    "capìscono": "capiscòno", "scrìvono": "scrivòno", "farmacìa": "farmàcia",
    "psicologìa": "psicològia", "brìndisi": "brindìsi", "famìglia": "famiglìa",
    "sùbito": "subìto", "subìto": "sùbito", "àncora": "ancòra", "ancòra": "àncora",
    "càpitano": "capitàno", "capitàno": "càpitano", "prìncipi": "princìpi", "princìpi": "prìncipi",
}
V2_TARGET = {plain(w): w for w in ["telèfonano", "parliàmo", "desìderano", "capìscono", "scrìvono",
                                   "farmacìa", "psicologìa", "brìndisi", "famìglia", "sùbito"]}
IT_HOMOGRAPHS = {"àncora", "ancòra", "càpitano", "capitàno", "prìncipi", "princìpi"}
IT_GLOSS = {"àncora": "якорь", "ancòra": "ещё", "prìncipi": "принцы", "princìpi": "принципы",
            "capitàno": "капитан", "càpitano": "случаются", "sùbito": "сразу", "subìto": "перенёс, пострадал от"}

# --- русский ------------------------------------------------------------------------------------
RU_CHOICES = {
    "zamok": ("зáмок — крепость", "замóк — на двери"),
    "plachu": ("плáчу — от слёз", "плачý — деньги"),
    "muka": ("мýка — страдание", "мукá — для теста (муку)"),
}
RU_EXPECT = {"zamok_1": 0, "zamok_2": 1, "plachu_1": 0, "plachu_2": 1, "muka_1": 0, "muka_2": 1}

# --- иврит --------------------------------------------------------------------------------------
HE_CHOICES = {
    "boker": ("בֹּקֶר, бóкер — утро", "בּוֹקֵר, бокéр — ковбой"),
    "okhel": ("אֹכֶל, óхель — еда", "אוֹכֵל, охéль — ест"),
    "sefer": ("סֵפֶר, сэ́фер — книга", "סַפָּר, сапáр — парикмахер"),
    "sapar": ("סֵפֶר, сэ́фер — книга", "סַפָּר, сапáр — парикмахер"),
    "banu": ("бáну — «в нас» (ударение на первый слог)", "банý — «построили» (ударение на последний)"),
    "shlomekh": ("шломéх — обращение к женщине", "шломхá — обращение к мужчине"),
    "shalom": ("шалóм — ударение на последний слог", "шáлом — ударение на первый слог"),
}
HE_EXPECT = {"boker_morning": 0, "boker_cowboy": 1, "okhel_food": 0, "okhel_eats": 1,
             "sefer_book": 0, "sapar_barber": 1, "banu_in_us": 0, "banu_built": 1, "shlomekh_fem": 0}

NUM = {"ноль": 0, "нуль": 0, "один": 1, "одна": 1, "первый": 1, "первая": 1, "два": 2, "две": 2,
       "второй": 2, "вторая": 2, "три": 3, "третий": 3, "третья": 3, "четыре": 4, "четвёртый": 4,
       "четвертый": 4, "пять": 5, "пятый": 5}


def choice_task(expert, question, options, expected):
    """options — список строк; expected — индекс верного или None. Перемешиваем порядок."""
    order = list(range(len(options)))
    random.shuffle(order)
    lines = [f"Вариант {i + 1}: {options[j]}" for i, j in enumerate(order)]
    exp = order.index(expected) + 1 if expected is not None else None
    return dict(expert=expert, kind="choice", question=INTRO + question + "\n" + "\n".join(lines) + "\n" + FORMAT_CHOICE,
                choices=" | ".join(lines), expected=exp, order=order)


def rate_task(expert, what):
    return dict(expert=expert, kind="rate", question=INTRO + what + "\n" + FORMAT_RATE,
                choices="", expected=None, order=None)


def build_task(r):
    sec, name, text, lang = r["section"], r["name"], r["text"], r["lang"]
    if name == "_reference" or sec == "cpu":
        return None
    parts = name.split("_")
    if sec in ("stress", "stress_v2"):
        # stress: имя base_<слово с грависом>_<none|grave|acute>_<solo|frame>; stress_v2: base_<none|grave>
        target = parts[1] if sec == "stress" else V2_TARGET.get(parts[0].lower())
        if not target or target.lower() not in IT_WRONG:
            return None
        target = target.lower()
        opts = [target, IT_WRONG[target]]
        gl = lambda w: f" ({IT_GLOSS[w]})" if w in IT_GLOSS else ""
        mark = "none" if "none" in parts else "mark"
        expected = None if (mark == "none" and target in IT_HOMOGRAPHS) else 0
        where = "в середине фразы" if "frame" in parts or sec == "stress_v2" else ""
        return choice_task("paolo", f"Как прочитано итальянское слово «{plain(target)}» {where}? "
                                    "Какой слог ударный?", [o + gl(o) for o in opts], expected)
    if sec == "it_context":
        target = parts[1].lower()
        return choice_task("paolo", f"Какое слово прозвучало во фразе — как оно произнесено?",
                           [f"{target} ({IT_GLOSS[target]})", f"{IT_WRONG[target]} ({IT_GLOSS[IT_WRONG[target]]})"], 0)
    if sec == "it_ambiguous":
        exp = {"plain": None, "princes": 0, "principles": 1}[name]
        return choice_task("paolo", "Что сказано во фразе «Ho visto i principi»?",
                           ["prìncipi (принцы)", "princìpi (принципы)"], exp)
    if sec == "geminates":
        a, b = parts[0], parts[1]
        opts = [f"сначала {a}, потом {b}", f"сначала {b}, потом {a}", f"оба раза {a}", f"оба раза {b}"]
        return choice_task("paolo", f"Слова отличаются только двойной согласной ({a} / {b}). "
                                    "Что ты слышишь, по порядку?", opts, 0)
    if sec in ("it_a1", "slow") or (sec == "clone" and lang == "it"):
        return rate_task("paolo", "Итальянская фраза. Оцени произношение.")
    if sec in ("mix",) or (sec == "clone" and lang == "ru"):
        return rate_task("paolo", "Русская фраза, возможно с итальянскими словами. Оцени произношение обоих языков.")
    if sec == "ru_repeat":
        return rate_task("paolo", "Русская фраза. Оцени произношение, особенно акцент и ударения.")
    if sec == "ru":
        key = next((k for k in RU_CHOICES if k in name), None)
        if key:
            suffix = name.split(key + "_")[-1]
            exp = RU_EXPECT.get(f"{key}_{suffix}")
            return choice_task("paolo", f"Русское слово «{plain(RU_CHOICES[key][0].split(' ')[0])}» — "
                                        "как оно произнесено?", list(RU_CHOICES[key]), exp)
        return rate_task("paolo", "Русская фраза. Оцени произношение.")
    if sec == "he_basic":
        return rate_task("hava", "Фраза на иврите. Оцени произношение.")
    if sec == "he_context":
        base = "_".join(parts[:2])
        return choice_task("hava", "Какое слово на иврите прозвучало во фразе?",
                           list(HE_CHOICES[parts[0]]), HE_EXPECT.get(base))
    if sec == "he_ambiguous":
        exp = {"plain": None, "morning": 0, "cowboy": 1}[name]
        return choice_task("hava", "Что сказано во фразе «הבוקר היה נחמד»?", list(HE_CHOICES["boker"]), exp)
    if sec == "he_stress":
        key = parts[0]
        exp = {"banu_plain": None, "banu_ole_first": 0, "shalom_plain": 0, "shalom_ole_wrong": 1}.get(name)
        return choice_task("hava", "Как произнесено это слово на иврите?", list(HE_CHOICES[key]), exp)
    return None


def parse(kind, text):
    t = text.lower().replace("ё", "е")
    key = "ответ" if kind == "choice" else "оценк"
    m = re.search(key + r"\w*\W{0,3}(\d|" + "|".join(sorted(NUM, key=len, reverse=True)) + ")", t)
    if not m:
        return None
    v = m.group(1)
    return int(v) if v.isdigit() else NUM.get(v)


def load_16k(path):
    try:
        import soundfile as sf
        y, sr = sf.read(path, dtype="float32")
    except ImportError:
        from scipy.io import wavfile
        sr, y = wavfile.read(path)
        y = y.astype(np.float32) / (32768.0 if y.dtype == np.int16 else 1.0)
    if y.ndim > 1:
        y = y.mean(axis=1)
    n = int(len(y) * 16000 / sr)
    y = np.interp(np.linspace(0, len(y) - 1, n), np.arange(len(y)), y)
    return list((np.clip(y, -1, 1) * 32767).astype(np.int16))


async def run_one(task, audio, keys, sem, timeout):
    ex = EXPERTS[task["expert"]]
    system = with_memory(open(ex["system"]).read(), ex["memory"])
    async with sem:
        for key in keys:
            try:
                return await listen(key, system, ex["voice"], audio, task["question"], timeout)
            except Exception as e:
                err = str(e)[:300]
        return f"[ошибка: {err}]"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--keys", default="~/key/key")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed)

    rows = list(csv.DictReader(open(os.path.join(a.root, "results.csv"))))
    only = set(filter(None, a.only.split(",")))
    jobs = []
    for r in rows:
        if only and r["section"] not in only:
            continue
        t = build_task(r)
        if t:
            jobs.append((r, t))
    if a.limit:
        jobs = jobs[:a.limit]
    print(f"заданий: {len(jobs)}", file=sys.stderr)

    keys = load_keys(a.keys)
    sem = asyncio.Semaphore(a.jobs)

    async def go(r, t):
        audio = load_16k(os.path.join(a.root, r["file"]))
        ans = await run_one(t, audio, keys, sem, a.timeout)
        got = parse(t["kind"], ans)
        ok = "" if t["expected"] is None or got is None else int(got == t["expected"])
        print(f"[{r['section']}] {r['name']}: {got} (ожидали {t['expected']}) {ans[:120]!r}", file=sys.stderr)
        return {**{k: r[k] for k in ("section", "name", "text", "lang", "tag", "file")},
                "expert": t["expert"], "kind": t["kind"], "choices": t["choices"],
                "expected": t["expected"], "answer": got, "correct": ok, "transcript": ans}

    out = await asyncio.gather(*(go(r, t) for r, t in jobs))
    path = os.path.join(a.root, "expert_results.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    agg = defaultdict(lambda: {"n": 0, "ok": 0, "judged": 0, "rates": []})
    for o in out:
        g = agg[(o["section"], o["expert"])]
        g["n"] += 1
        if o["kind"] == "choice" and o["correct"] != "":
            g["judged"] += 1
            g["ok"] += o["correct"]
        if o["kind"] == "rate" and o["answer"]:
            g["rates"].append(o["answer"])
    lines = ["| раздел | эксперт | записей | верно / с эталоном | средняя оценка |", "|---|---|---|---|---|"]
    for (sec, ex), g in agg.items():
        acc = f"{g['ok']} / {g['judged']}" if g["judged"] else "—"
        rate = f"{sum(g['rates']) / len(g['rates']):.1f}" if g["rates"] else "—"
        lines.append(f"| {sec} | {ex} | {g['n']} | {acc} | {rate} |")
    open(os.path.join(a.root, "expert_summary.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
