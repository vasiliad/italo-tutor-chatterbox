#!/usr/bin/env python3
"""Набор тестов для сравнения локальных TTS (продолжение проверки Chatterbox, см. italo-tutor
docs/research/local_tts_2026.md). Пишет tts_eval/testset.json.

Итальянский — три варианта ввода:
  plain  — обычный текст;
  accent — ударение знаком на гласной (grave — открытая/i/u/a, acute — закрытые é/ó), как у нас в словаре;
  ipa    — фонемы espeak-ng из текста с акцентами (как есть);
  ipa_len — только it_gem: геминаты единообразно через ː (CC → Cː, rɾ → rː);
  ipa_word / ipa_len_word — [слово, IPA] для проверяемого слова: текст, где только это слово дано фонемами.
Русский: plain и accent (U+0301), IPA — вручную только для проверочного слова (espeak знак игнорирует).
Иврит: plain и с огласовками (niqqud) вручную.
  python3 tts_eval/testset.py        # нужен espeak-ng (apt install espeak-ng)
"""
import json
import os
import re
import subprocess
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))


def espeak_ipa(text):
    """IPA espeak-ng как есть (на таком обучены Kokoro/Piper): геминаты то удвоением, то ː."""
    out = subprocess.run(["espeak-ng", "-q", "-v", "it", "--ipa", text],
                         capture_output=True, text=True, check=True).stdout
    return " ".join(out.split())


def long_ipa(ipa):
    """Геминаты единообразно через ː (второй способ записи — только для раздела it_gem)."""
    ipa = ipa.replace("rɾ", "rː")
    # удвоенная согласная → согласная + ː (espeak пишет сонорные удвоением, смычные через ː)
    ipa = re.sub(r"([bcdfɡkʎlmnɲpqrsʃtvzʒ])\1", r"\1ː", ipa)
    return ipa


def plain(s):
    """Снять знаки ударения с итальянского текста, кроме конечных (città, perché, caffè)."""
    out = []
    for word in re.findall(r"\w+|\W+", s):
        d = unicodedata.normalize("NFD", word)
        if word and word[-1].lower() in "àèéìíòóùú":
            out.append(word)
        else:
            out.append(unicodedata.normalize("NFC", "".join(c for c in d if c not in "̀́")))
    return "".join(out)


items = []


def it(section, name, accented, expected="", note="", target=None):
    """target — проверяемое слово (с акцентом): для моделей, которым IPA дают только на это слово в тексте."""
    ipa = espeak_ipa(accented)
    inputs = {"plain": plain(accented), "accent": accented, "ipa": ipa}
    if section == "it_gem":
        inputs["ipa_len"] = long_ipa(ipa)
    if target is None and accented.startswith("Dico ") and accented.endswith(" adesso."):
        target = accented[5:-8]
    if target:
        wi = espeak_ipa(f"Dico {target} adesso.").split()[1]  # в рамке: без «изолированного» ɪ на конце
        inputs["ipa_word"] = [plain(target), wi]
        if section == "it_gem":
            inputs["ipa_len_word"] = [plain(target), long_ipa(wi)]
    items.append(dict(id=f"{section}__{name}", section=section, lang="it", expected=expected, note=note,
                      inputs=inputs))


# 1. Омографы во фразе с контекстом (Chatterbox: 16/16 по контексту)
for name, s, exp in [
    ("ancora_ancora", "Vorrei ancóra un caffè.", "ancóra — ещё"),
    ("ancora_ancora2", "La nave getta l'àncora in porto.", "àncora — якорь"),
    ("principi_principles", "I princìpi della fìsica sono sèmplici.", "princìpi — принципы"),
    ("principi_princes", "Il re e la regina hanno due figli: sono prìncipi.", "prìncipi — принцы"),
    ("capitano_captain", "Il capitàno parla con i marinài.", "capitàno — капитан"),
    ("capitano_happen", "Queste cose càpitano spesso.", "càpitano — случаются"),
    ("subito_soon", "Vieni sùbito qui!", "sùbito — сразу"),
    ("subito_suffered", "Ha subìto un furto ieri sera.", "subìto — пострадал"),
]:
    it("it_context", name, s, exp, target=exp.split(" — ")[0])

# 2. Омографы без контекста: слово в пустой рамке — решает только разметка (Chatterbox: угадывание)
for w, exp in [("àncora", "якорь"), ("ancóra", "ещё"), ("prìncipi", "принцы"), ("princìpi", "принципы"),
               ("càpitano", "случаются"), ("capitàno", "капитан"), ("sùbito", "сразу"), ("subìto", "пострадал"),
               ("ìndice", "указатель — ударение на 1-м"), ("àrbitro", "судья — ударение на 1-м")]:
    it("it_solo", plain(w).lower() + "_" + exp.split()[0], f"Dico {w} adesso.", w, exp)

# 3. Трудные слова (ошибки Паоло и типичные русские ошибки)
for w in ["telèfonano", "desìderano", "capìscono", "scrìvono", "farmacìa", "psicologìa", "Brìndisi",
          "zùcchero", "tàvolo", "piròscafo", "leggère", "lèggere"]:
    it("it_stress", plain(w).lower() + ("_2" if w == "lèggere" else ""), f"Dico {w} adesso.", w)

# 4. Двойные согласные: каждое слово отдельно, чтобы судья сказал «одна или две»
for a, b in [("caro", "carro"), ("pala", "palla"), ("séte", "sètte"), ("capéllo", "cappèllo"),
             ("fàto", "fàtto"), ("pàpa", "pàppa"), ("nòno", "nònno")]:
    for w, g in [(a, "single"), (b, "double")]:
        it("it_gem", f"{plain(a)}_{plain(b)}__{plain(w)}", f"Dico {w} adesso.", g, f"{plain(a)} / {plain(b)}")

# 5. Фразы A1 (качество речи)
for i, s in enumerate([
    "Ciào, mi chiàmo Pàolo. Come ti chiàmi?", "Piacére! Sono russa, di Mosca.",
    "Vorrèi un caffè e un cornétto, per favóre.", "Quanto còsta questo libro?",
    "Dov'è la stazióne? È lontàna da qui?", "C'è una farmacìa vicino all'albèrgo?",
    "Ho ventitré anni e àbito a Mosca.", "Ièri ho mangiàto la pizza con i miei amìci.",
    "Scusi, a che óra parte il treno per Firènze?", "Domàni andiàmo al mare, se non piòve."]):
    it("it_a1", f"{i:02d}", s)

# 6. Русский: ударение знаком U+0301 и вручную IPA только для проверочного слова
A = "́"
for name, text, word, ipa, exp in [
    ("zamok_castle", f"Это старый за{A}мок.", f"за{A}мок", "ˈzamək", "за́мок — крепость"),
    ("zamok_lock", f"Это старый замо{A}к.", f"замо{A}к", "zɐˈmok", "замо́к — на двери"),
    ("plachu_cry", f"Я пла{A}чу, когда слушаю эту песню.", f"пла{A}чу", "ˈplat͡ɕʊ", "пла́чу — от слёз"),
    ("plachu_pay", f"Я плачу{A} за кофе.", f"плачу{A}", "plɐˈt͡ɕu", "плачу́ — деньги"),
    ("muka_pain", f"Это была настоящая му{A}ка.", f"му{A}ка", "ˈmukə", "му́ка — страдание"),
    ("muka_flour", f"Купи муку{A} для пиццы.", f"муку{A}", "mʊˈku", "муку́ — для теста"),
]:
    p = text.replace(A, "")
    items.append(dict(id=f"ru__{name}", section="ru", lang="ru", expected=exp, note="",
                      inputs={"plain": p, "accent": text, "ipa_word": [word.replace(A, ""), ipa]}))
items.append(dict(id="ru__phrase", section="ru", lang="ru", expected="", note="",
                  inputs={"plain": "Сегодня мы говорим о прошедшем времени. Это совсем не сложно."}))

# 7. Иврит: без огласовок и с огласовками (вручную, верное слово)
for name, p, n, exp in [
    ("boker_morning", "בוקר טוב!", "בֹּקֶר טוֹב!", "бóкер — утро"),
    ("boker_cowboy", "הבוקר רכב על סוס.", "הַבּוֹקֵר רָכַב עַל סוּס.", "бокéр — ковбой"),
    ("okhel_food", "האוכל על השולחן.", "הָאֹכֶל עַל הַשֻּׁלְחָן.", "óхель — еда"),
    ("okhel_eats", "הוא אוכל לחם.", "הוּא אוֹכֵל לֶחֶם.", "охéль — ест"),
    ("sefer_book", "אני קורא ספר.", "אֲנִי קוֹרֵא סֵפֶר.", "сэ́фер — книга"),
    ("sapar_barber", "הספר גזר לי את השיער.", "הַסַּפָּר גָּזַר לִי אֶת הַשֵּׂעָר.", "сапáр — парикмахер"),
    ("shalom", "שלום, מה שלומך?", "שָׁלוֹם, מַה שְּׁלוֹמֵךְ?", "шломéх — к женщине"),
]:
    items.append(dict(id=f"he__{name}", section="he", lang="he", expected=exp, note="",
                      inputs={"plain": p, "niqqud": n}))

json.dump(items, open(os.path.join(HERE, "testset.json"), "w"), ensure_ascii=False, indent=1)
print(len(items), "пунктов")
