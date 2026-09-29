#!/usr/bin/env python3
"""Акустическая проверка ударения и долготы согласных — без судьи-LLM.

Судья Gemini не различает омографы без контекста: побеждает частое слово (results/2026-09-29_local_tts).
Здесь меряем сам звук:
1. Распознаватель по буквам (wav2vec2 XLSR-53 it/ru, CTC) размечает запись по известному тексту
   (принудительное выравнивание, свой Витерби). Получаем начало каждой буквы; гласная длится до начала следующей буквы.
2. Для каждой гласной проверяемого слова: длительность, громкость (RMS, дБ) и высота тона (pyin),
   нормированные внутри слова (z-оценки). Ударность = z_длит + z_громк + z_тон.
3. Из двух кандидатов (задуманное ударение и «неверное» / второе слово омографа) ударной считается та гласная,
   у которой ударность выше. Геминаты: длительность согласной / длительность предыдущей гласной;
   у пары (caro/carro) в одной модели и одном виде ввода двойная должна быть длиннее.
Эталон, по которому видно, работает ли сама мера: Piper и Kokoro с IPA — фонемы там выполняются буквально.

  python3 tts_eval/stress_probe.py --out <out с <модель>/asr.csv и WAV>   → out/stress_probe.csv и .md
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

import librosa
import numpy as np
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from expert_tts import WRONG, accented_target  # noqa: E402

CTC = {"it": "jonatasgrosman/wav2vec2-large-xlsr-53-italian", "ru": "jonatasgrosman/wav2vec2-large-xlsr-53-russian"}
VOWELS = {"it": set("aeiouàèéìíòóùú"), "ru": set("аеёиоуыэюя")}
HOP = 0.02  # шаг кадра wav2vec2, с


def stress_index(accented):
    """Индекс ударной гласной в слове без знаков: àncora → 0, ancóra → 3."""
    d = unicodedata.normalize("NFD", accented)
    i = 0
    for k, c in enumerate(d):
        if unicodedata.combining(c):
            if c in "̀́":
                return i - 1
            continue
        i += 1
    return None


def norm_text(s, lang):
    s = s.lower().replace("’", "'")
    if lang == "it":  # внутри слов знаки ударения снимаем, конечные (città, caffè) — в словаре модели
        s = "".join(w if w and w[-1] in "àèéìíòóùú" else
                    unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", w) if c not in "̀́"))
                    for w in re.findall(r"\w+|\W+", s))
    else:
        s = s.replace("́", "")
    s = re.sub(r"[^\w' ]+", " ", s)
    return " ".join(s.split())


def viterbi(logp, tokens, blank):
    """CTC-выравнивание: для каждого токена — первый кадр, где он звучит."""
    T, L = logp.shape[0], 2 * len(tokens) + 1
    ext = [blank if i % 2 == 0 else tokens[i // 2] for i in range(L)]
    NEG = -1e9
    dp = np.full((T, L), NEG)
    bp = np.zeros((T, L), dtype=np.int32)
    dp[0, 0] = logp[0, ext[0]]
    dp[0, 1] = logp[0, ext[1]]
    for t in range(1, T):
        for s in range(L):
            cands = [(dp[t - 1, s], s)]
            if s >= 1:
                cands.append((dp[t - 1, s - 1], s - 1))
            if s >= 2 and ext[s] != blank and ext[s] != ext[s - 2]:
                cands.append((dp[t - 1, s - 2], s - 2))
            v, p = max(cands)
            dp[t, s] = v + logp[t, ext[s]]
            bp[t, s] = p
    s = L - 1 if dp[T - 1, L - 1] >= dp[T - 1, L - 2] else L - 2
    path = [s]
    for t in range(T - 1, 0, -1):
        s = bp[t, s]
        path.append(s)
    path = path[::-1]
    start = [None] * len(tokens)
    for t, s in enumerate(path):
        if s % 2 == 1 and start[s // 2] is None:
            start[s // 2] = t
    return start, T


class Aligner:
    def __init__(self, lang):
        self.proc = Wav2Vec2Processor.from_pretrained(CTC[lang])
        self.model = Wav2Vec2ForCTC.from_pretrained(CTC[lang]).eval()
        self.vocab = self.proc.tokenizer.get_vocab()
        self.blank = self.vocab["<pad>"]

    def align(self, y, text):
        """[(буква, начало_с, конец_с)] для text (пробел — '|')."""
        with torch.inference_mode():
            logits = self.model(self.proc(y, sampling_rate=16000, return_tensors="pt").input_values).logits[0]
        logp = torch.log_softmax(logits, -1).numpy()
        chars = list(text.replace(" ", "|"))
        toks = [self.vocab.get(c, self.vocab["<unk>"]) for c in chars]
        if logp.shape[0] < len(toks) * 2:
            return None
        start, T = viterbi(logp, toks, self.blank)
        out = []
        for i, c in enumerate(chars):
            b = start[i] * HOP
            e = (start[i + 1] if i + 1 < len(chars) else T) * HOP
            out.append((c, b, e))
        return out


def vowel_feats(y, sr, segs, f0):
    """Для сегментов гласных: длительность, RMS дБ, медиана f0 (Гц, nan если глухо)."""
    res = []
    for b, e in segs:
        a, z = int(b * sr), max(int(e * sr), int(b * sr) + 1)
        x = y[a:z]
        rms = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-6)
        fr = f0[int(b / 0.01):max(int(e / 0.01), int(b / 0.01) + 1)]
        fr = fr[~np.isnan(fr)]
        res.append((e - b, rms, float(np.median(fr)) if len(fr) else np.nan))
    return np.array(res)


def z(v):
    v = np.asarray(v, float)
    if np.all(np.isnan(v)):
        return np.zeros_like(v)
    m, s = np.nanmean(v), np.nanstd(v)
    return np.nan_to_num((v - m) / (s if s > 1e-9 else 1.0))


def word_span(al, text, word):
    """Индексы букв слова word в выравнивании (первое вхождение целым словом)."""
    t = text.replace(" ", "|")
    m = re.search(rf"(?:^|\|){re.escape(word)}(?:\||$)", t)
    if not m:
        return None
    s = m.start() + (1 if t[m.start()] == "|" else 0)
    return list(range(s, s + len(word)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="")
    a = ap.parse_args()
    items = {x["id"]: x for x in json.load(open(os.path.join(HERE, "testset.json")))}
    aligners = {}
    rows = []
    models = [m for m in sorted(os.listdir(a.out)) if os.path.exists(os.path.join(a.out, m, "asr.csv"))]
    if a.models:
        models = [m for m in models if m in a.models.split(",")]
    for m in models:
        for r in csv.DictReader(open(os.path.join(a.out, m, "asr.csv"))):
            it = items[r["id"]]
            sec, lang = it["section"], it["lang"]
            if sec not in ("it_solo", "it_stress", "it_context", "it_gem", "ru") or "ipa_word" not in it["inputs"]:
                continue
            word = norm_text(it["inputs"]["ipa_word"][0], lang)
            text = norm_text(it["inputs"]["plain"], lang)
            y, sr = librosa.load(os.path.join(a.out, m, r["wav"]), sr=16000)
            if lang not in aligners:
                aligners[lang] = Aligner(lang)
            al = aligners[lang].align(y, text)
            span = word_span(al, text, word) if al else None
            row = dict(model=m, id=r["id"], section=sec, lang=lang, variant=r["variant"], cer=r["cer"],
                       word=word, predicted="", expected="", correct="", ratio="", note="")
            if not span:
                row["note"] = "не выровнялось"
                rows.append(row)
                continue
            f0, _, _ = librosa.pyin(y, fmin=70, fmax=450, sr=sr, hop_length=160)
            vidx = [k for k, i in enumerate(span) if al[i][0] in VOWELS[lang]]
            if sec == "it_gem":
                # двойная/одинарная: первая согласная после первой гласной слова до следующей гласной
                v0 = vidx[0]
                c0 = v0 + 1
                v1 = next(k for k in vidx if k > c0)
                cons = al[span[v1]][1] - al[span[c0]][1]
                vow = al[span[c0]][1] - al[span[v0]][1]
                row.update(ratio=round(cons / max(vow, 0.02), 3), expected=it["expected"])
                rows.append(row)
                continue
            if lang == "it":
                good = accented_target(it)
                cand = [stress_index(good), stress_index(WRONG[good])]
            else:
                acc = next(w for w in it["inputs"]["accent"].split() if "́" in w)
                gi = stress_index(acc.lower())
                cand = [gi, next(k for k in vidx if k != gi)]
            feats = vowel_feats(y, sr, [(al[span[k]][1], al[span[k]][2]) for k in vidx], f0)
            score = z(feats[:, 0]) + z(feats[:, 1]) + z(feats[:, 2])
            sc = {k: s for k, s in zip(vidx, score)}
            if cand[0] not in sc or cand[1] not in sc:
                row["note"] = f"кандидаты не гласные {cand}"
                rows.append(row)
                continue
            pred = 0 if sc[cand[0]] >= sc[cand[1]] else 1
            row.update(predicted=pred, expected=0, correct=int(pred == 0),
                       ratio=round(float(sc[cand[0]] - sc[cand[1]]), 2))
            rows.append(row)
        print(m, sum(1 for x in rows if x["model"] == m), flush=True)
    path = os.path.join(a.out, "stress_probe.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summarize(rows, a.out)


def summarize(rows, out):
    md = ["# Акустическая проверка ударения и долготы\n",
          "Ударение: доля записей, где задуманная гласная акустически ударнее «неверной» (длительность + громкость + тон).",
          "Геминаты: доля пар (одна модель, один вид ввода), где у двойной согласной отношение C/V больше, чем у одинарной.\n",
          "Пары омографов: àncora/ancóra и т. п. в одной модели и одном виде ввода — разность «ударности» задуманной и",
          "другой гласной, сложенная по паре, должна быть > 0 (сравнение внутри пары снимает разницу гласных и сдвиги разметки).\n",
          "| модель | вариант | ударение it (solo+stress+context) | омографы без контекста (it_solo) | пары омографов | ru | геминаты (пары) |",
          "|---|---|---|---|---|---|---|"]
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    gem = defaultdict(dict)
    hom = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["section"] != "it_gem" and r["ratio"] != "" and r["lang"] == "it":
            hom[(r["model"], r["variant"])][(r["section"], r["word"])].append(float(r["ratio"]))
        k = (r["model"], r["variant"])
        if r["section"] == "it_gem" and r["ratio"] != "":
            pair = r["id"].rsplit("__", 1)[0]
            gem[k].setdefault(pair, {})[r["expected"]] = float(r["ratio"])
        elif r["correct"] != "":
            for g in (["it"] if r["lang"] == "it" else ["ru"]) + (["solo"] if r["section"] == "it_solo" else []):
                agg[k][g][0] += r["correct"]
                agg[k][g][1] += 1
    fmt = lambda x: f"{x[0]}/{x[1]} ({round(100 * x[0] / x[1])}%)" if x[1] else ""
    for k in sorted(set(agg) | set(gem)):
        pairs = [p for p in gem[k].values() if "single" in p and "double" in p]
        g = [sum(p["double"] > p["single"] for p in pairs), len(pairs)]
        hp = [v for v in hom[k].values() if len(v) == 2]
        h = [sum(sum(v) > 0 for v in hp), len(hp)]
        md.append(f"| {k[0]} | {k[1]} | {fmt(agg[k]['it'])} | {fmt(agg[k]['solo'])} | {fmt(h)} | {fmt(agg[k]['ru'])} | {fmt(g)} |")
    open(os.path.join(out, "stress_probe.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
