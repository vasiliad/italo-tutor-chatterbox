#!/usr/bin/env python3
"""Слепая экспертиза на слух записей tts_eval: Паоло (it, ru) и Хава (he) на gemini-3.8-live.

Эксперт слышит запись и выбирает из вариантов (порядок перемешан), что прозвучало: какой слог ударный,
какое слово омографа, одна или две согласные. Что задумано, он не знает. Ответ сравнивается с задуманным.
Спрашиваем только то, что проверяет управление произношением (ударения, омографы, геминаты, ru/he пары);
фразы A1 — оценка 1–5 для немногих вариантов. Целая фраза в IPA у MOSS не распознаётся (CER ≥ 0.45) — пропускаем.

  python3 tts_eval/expert_tts.py --out <папка out с <модель>/asr.csv и WAV> [--limit N] [--per-min 20]

Ключи — ~/key/key (по одному в строке, из разных проектов: у каждого ключа свой темп и свой поток).
Ответы — out/expert_tts.csv (продолжение после обрыва), сводка — out/expert_tts.md.
"""
import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools", "expert"))
from expert_listen import INTRO, Pacer, choice_task, load_16k, parse, rate_task, run_one, stressed  # noqa: E402
from paolo import load_keys  # noqa: E402

MODEL = "models/gemini-3.8-live"
# слово с ударением (как в testset) → неверное прочтение или второе слово омографа; перевод
WRONG = {
    "àncora": "ancóra", "ancóra": "àncora", "prìncipi": "princìpi", "princìpi": "prìncipi",
    "càpitano": "capitàno", "capitàno": "càpitano", "sùbito": "subìto", "subìto": "sùbito",
    "ìndice": "indìce", "àrbitro": "arbìtro", "telèfonano": "telefònano", "desìderano": "desidèrano",
    "capìscono": "capiscòno", "scrìvono": "scrivòno", "farmacìa": "farmàcia", "psicologìa": "psicològia",
    "brìndisi": "brindìsi", "zùcchero": "zucchèro", "tàvolo": "tavòlo", "piròscafo": "piroscàfo",
    "leggère": "lèggere", "lèggere": "leggère",
}
GLOSS = {"àncora": "якорь", "ancóra": "ещё", "prìncipi": "принцы", "princìpi": "принципы",
         "capitàno": "капитан", "càpitano": "случаются", "sùbito": "сразу", "subìto": "пострадал от",
         "leggère": "лёгкие", "lèggere": "читать"}
HOMOGRAPHS = {"àncora", "ancóra", "prìncipi", "princìpi", "càpitano", "capitàno", "sùbito", "subìto",
              "leggère", "lèggere"}
RU = {"zamok": ("зáмок — крепость", "замóк — на двери"), "plachu": ("плáчу — от слёз", "плачý — деньги"),
      "muka": ("мýка — страдание", "мукá — для теста (муку)")}
RU_EXP = {"castle": 0, "lock": 1, "cry": 0, "pay": 1, "pain": 0, "flour": 1}
HE = {"boker": ("בֹּקֶר, бóкер — утро", "בּוֹקֵר, бокéр — ковбой"),
      "okhel": ("אֹכֶל, óхель — еда", "אוֹכֵל, охéль — ест"),
      "sefer": ("סֵפֶר, сэ́фер — книга", "סַפָּר, сапáр — парикмахер"),
      "sapar": ("סֵפֶר, сэ́фер — книга", "סַפָּר, сапáр — парикмахер"),
      "shalom": ("шломéх — обращение к женщине", "шломхá — обращение к мужчине")}
HE_EXP = {"boker_morning": 0, "boker_cowboy": 1, "okhel_food": 0, "okhel_eats": 1, "sefer_book": 0,
          "sapar_barber": 1, "shalom": 0}
# номер ударного слога с начала слова (режим --syllable: слово не показываем — нет подсказки «частым словом»)
SYLLABLE = {"àncora": 1, "ancóra": 2, "prìncipi": 1, "princìpi": 2, "càpitano": 1, "capitàno": 3, "sùbito": 1,
            "subìto": 2, "ìndice": 1, "àrbitro": 1, "telèfonano": 2, "desìderano": 2, "capìscono": 2, "scrìvono": 1,
            "farmacìa": 3, "psicologìa": 4, "brìndisi": 1, "zùcchero": 1, "tàvolo": 1, "piròscafo": 2,
            "leggère": 2, "lèggere": 1}
RU_SYL = {"castle": 1, "lock": 2, "cry": 1, "pay": 2, "pain": 1, "flour": 2}
BLIND_END = (" Слово я не называю — суди только по звуку. Ответь строго так: «Ответ: <номер>», потом одной фразой — "
             "что ты услышал. Если не можешь различить — «Ответ: ноль».")


def syl_q(where):
    return (f"Слушай {where}. Какой по счёту слог в нём ударный, если считать с начала слова: 1, 2, 3 или 4?" + BLIND_END)


def word_pos(item):
    """Номер слова (с 1) в обычном тексте, где стоит проверяемое слово (l'ancora — одно слово)."""
    w = item["inputs"]["ipa_word"][0].lower()
    toks = item["inputs"]["plain"].lower().split()
    return next(i for i, t in enumerate(toks, 1) if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", t))
PRIORITY = ["it_solo", "it_stress", "it_context", "it_gem", "ru", "he", "it_a1"]
RATE_VARIANTS = {"plain", "clone"}  # фразы A1 — оценка только для обычного текста и клона


def plain(s):
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", s)
                                                if unicodedata.category(c) != "Mn"))


def accented_target(item):
    """Проверяемое слово с ударением: из рамки «Dico X adesso.» или из ожидаемого «X — перевод»."""
    a = item["inputs"]["accent"]
    if a.startswith("Dico ") and a.endswith(" adesso."):
        return a[5:-8].lower()
    return item["expected"].split(" — ")[0].lower()


def blind(item, variant):
    """Слепой режим: всё слушает Паоло, варианты-слова не показываем (иначе он выбирает частое слово)."""
    sec = item["section"]
    task = lambda q, exp, ch: dict(expert="paolo", kind="choice", question=INTRO + q, choices=ch, expected=exp, order=None)
    if sec in ("it_solo", "it_stress"):
        return task(syl_q("только среднее слово во фразе «Dico … adesso»"), SYLLABLE[accented_target(item)], "слог")
    if sec == "it_context":
        n = word_pos(item)
        return task(syl_q(f"итальянскую фразу; нас интересует слово номер {n}, если считать слова с начала фразы"),
                    SYLLABLE[accented_target(item)], f"слог, слово {n}")
    if sec == "it_gem":
        return task("Слушай только среднее слово во фразе «Dico … adesso». Есть ли в нём двойная (долгая, удвоенная) "
                    "согласная? Вариант 1 — нет, все согласные короткие. Вариант 2 — да, есть долгая согласная." + BLIND_END,
                    1 if item["expected"] == "single" else 2, "1 одинарная | 2 двойная")
    if sec == "ru" and "ipa_word" in item["inputs"]:
        n = word_pos(item)
        return task(syl_q(f"русскую фразу; нас интересует слово номер {n}, если считать слова с начала фразы"),
                    RU_SYL[item["id"].rsplit("_", 1)[-1]], f"слог, слово {n}")
    if sec == "ru":
        return rate_task("paolo", "Русская фраза. Оцени произношение, особенно ударения и акцент.")
    if sec == "it_a1":
        return rate_task("paolo", "Итальянская фраза. Оцени произношение.")
    return None  # иврит — не к Паоло


def build(item, variant, syllable=False):
    sec = item["section"]
    if syllable:
        return blind(item, variant)
    if sec in ("it_solo", "it_stress", "it_context"):
        t = accented_target(item)
        if t not in WRONG:
            return None
        expected = 0
        if variant == "plain" and sec == "it_solo" and t in HOMOGRAPHS:
            expected = None  # без разметки и без контекста «верного» нет — смотрим, что выберет модель
        gl = lambda w: f" — ударная гласная {stressed(w)}" + (f", «{GLOSS[w]}»" if w in GLOSS else "")
        where = "во фразе" if sec == "it_context" else "в середине фразы «Dico … adesso»"
        return choice_task("paolo", f"Как прочитано итальянское слово «{plain(t)}» {where}? Какой слог ударный? "
                                    "Сначала реши, какую гласную ты слышишь ударной, потом найди вариант с ней.",
                           [t + gl(t), WRONG[t] + gl(WRONG[t])], expected)
    if sec == "it_gem":
        a, b = [w.strip() for w in item["note"].split("/")]
        exp = 0 if item["expected"] == "single" else 1
        return choice_task("paolo", f"В середине фразы «Dico … adesso» прозвучало «{a}» или «{b}»? "
                                    "Слушай только, одна согласная или двойная (долгая).",
                           [f"{a} — одна согласная", f"{b} — двойная, долгая согласная"], exp)
    if sec == "ru":
        key = next((k for k in RU if f"__{k}_" in item["id"]), None)
        if not key:
            return rate_task("paolo", "Русская фраза. Оцени произношение.") if variant in RATE_VARIANTS else None
        return choice_task("paolo", f"Русское слово «{item['inputs']['ipa_word'][0]}» — как оно произнесено?",
                           list(RU[key]), RU_EXP[item["id"].rsplit("_", 1)[-1]])
    if sec == "he":
        name = item["id"].split("__", 1)[1]
        return choice_task("hava", "Какое слово на иврите прозвучало во фразе? Как оно произнесено?",
                           list(HE[name.split("_")[0]]), HE_EXP[name])
    if sec == "it_a1" and variant in RATE_VARIANTS:
        return rate_task("paolo", "Итальянская фраза. Оцени произношение.")
    return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--per-min", type=float, default=20, help="на ключ (ключи из разных проектов)")
    ap.add_argument("--keys", default="~/key/key")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--syllable", action="store_true",
                    help="слепой режим: все записи, только Паоло; номер ударного слога / есть ли долгая согласная, слов не показываем")
    a = ap.parse_args()
    random.seed(a.seed)
    items = {x["id"]: x for x in json.load(open(os.path.join(HERE, "testset.json")))}

    jobs = []
    for f in sorted(os.listdir(a.out)):
        p = os.path.join(a.out, f, "asr.csv")
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            if r["variant"] in ("ipa", "ipa_len") and f.startswith("moss") and not a.syllable:
                continue  # фраза целиком в IPA у MOSS неразборчива (в слепом режиме слушаем всё)
            t = build(items[r["id"]], r["variant"], a.syllable)
            if t:
                jobs.append((f, r, t))
    # по приоритету раздела, внутри — модели вперемешку (частичный итог сравним по моделям)
    random.shuffle(jobs)
    jobs.sort(key=lambda j: PRIORITY.index(j[1]["section"]))
    if a.limit:
        jobs = jobs[:a.limit]

    tag = "_syllable" if a.syllable else ""
    path = os.path.join(a.out, f"expert_tts{tag}.csv")
    fields = ["model", "id", "section", "lang", "variant", "cer", "expert", "kind", "choices", "expected",
              "answer", "correct", "transcript"]
    done = {}
    if os.path.exists(path):
        done = {(o["model"], o["id"], o["variant"]): o for o in csv.DictReader(open(path))
                if not o["transcript"].startswith("[")}
    todo = [j for j in jobs if (j[0], j[1]["id"], j[1]["variant"]) not in done]
    keys = load_keys(a.keys)
    print(f"заданий {len(jobs)}, уже есть {len(jobs) - len(todo)}, ключей {len(keys)}, модель {a.model}", flush=True)

    results = dict(done)
    lock = asyncio.Lock()
    queue = asyncio.Queue()
    for j in todo:
        queue.put_nowait(j)
    counter = [0]

    def save():
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fields)
            w.writeheader()
            w.writerows(results.values())

    async def worker(idx):
        pacer = Pacer(a.per_min)
        while not queue.empty():
            model, r, t = queue.get_nowait()
            audio = load_16k(os.path.join(a.out, model, r["wav"]))
            ans = await run_one(t, audio, [keys[idx]], [pacer], 0, a.timeout, False, a.model)
            got = parse(t["kind"], ans)
            ok = "" if t["expected"] is None or got is None else int(got == t["expected"])
            async with lock:
                results[(model, r["id"], r["variant"])] = dict(
                    model=model, id=r["id"], section=r["section"], lang=r["lang"], variant=r["variant"],
                    cer=r["cer"], expert=t["expert"], kind=t["kind"], choices=t["choices"], expected=t["expected"],
                    answer=got if got is not None else "", correct=ok, transcript=ans)
                counter[0] += 1
                print(f"{counter[0]}/{len(todo)} k{idx} {model} {r['id']} {r['variant']}: {got} (ждали {t['expected']}) "
                      f"{ans[:90]!r}", flush=True)
                if counter[0] % 20 == 0:
                    save()

    await asyncio.gather(*(worker(i) for i in range(len(keys))))
    save()
    summarize(list(results.values()), a.out, a.model, tag)


def summarize(rows, out, model, tag=""):
    agg = defaultdict(lambda: {"n": 0, "ok": 0, "judged": 0, "rates": [], "free": defaultdict(int)})
    for o in rows:
        g = agg[(o["model"], o["section"], o["variant"])]
        g["n"] += 1
        if o["kind"] == "choice":
            if str(o["correct"]) in ("0", "1"):
                g["judged"] += 1
                g["ok"] += int(o["correct"])
            elif o["expected"] in ("", None) and str(o["answer"]).isdigit():
                g["free"][int(o["answer"])] += 1
        elif str(o["answer"]).isdigit():
            g["rates"].append(int(o["answer"]))
    md = [f"# Экспертиза на слух ({model})\n",
          "Верно — эксперт выбрал задуманное (ударение / слово / одна-две согласные). Оценка 1–5 — фразы A1.\n",
          "## Итог по моделям (ударение и омографы it: it_solo + it_stress + it_context)\n",
          "| модель | вариант | верно | % | геминаты | ru | he | оценка A1 |", "|---|---|---|---|---|---|---|---|"]
    models = sorted({k[0] for k in agg})
    for m in models:
        for v in sorted({k[2] for k in agg if k[0] == m}):
            s = [agg[(m, sec, v)] for sec in ("it_solo", "it_stress", "it_context") if (m, sec, v) in agg]
            ok, j = sum(g["ok"] for g in s), sum(g["judged"] for g in s)
            cell = lambda sec: (f"{agg[(m, sec, v)]['ok']}/{agg[(m, sec, v)]['judged']}"
                                if (m, sec, v) in agg and agg[(m, sec, v)]["judged"] else "")
            r = agg.get((m, "it_a1", v), {}).get("rates") if (m, "it_a1", v) in agg else []
            md.append(f"| {m} | {v} | {ok}/{j} | {round(100 * ok / j) if j else ''} | {cell('it_gem')} | {cell('ru')} | "
                      f"{cell('he')} | {round(sum(r) / len(r), 1) if r else ''} |")
    md += ["\n## По разделам\n", "| модель | раздел | вариант | n | верно / с эталоном |", "|---|---|---|---|---|"]
    for (m, sec, v), g in sorted(agg.items()):
        md.append(f"| {m} | {sec} | {v} | {g['n']} | {g['ok']}/{g['judged']} |")
    open(os.path.join(out, f"expert_tts{tag}.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md[:4 + 2 + 40]))


if __name__ == "__main__":
    asyncio.run(main())
