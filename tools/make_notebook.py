import json, sys

cells = []
def md(s): cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})

md(r"""
# Chatterbox Multilingual: проверка для italo-tutor

Отчёт о модели: `docs/research/chatterbox_tts.md`. Инструкция по запуску: `tools/kaggle/README.md`.

**Настройки Kaggle:** Internet = **On**. Подойдёт любой ускоритель: ноутбук сам выберет CUDA, если torch 2.6
её поддерживает, иначе CPU (все ядра). На CPU полный прогон долгий, поэтому там по умолчанию `QUICK = True`: меньше записей.
Записи Паоло для клонирования ноутбук берёт из репозитория
[vasiliad/italo-tutor-chatterbox](https://github.com/vasiliad/italo-tutor-chatterbox) (`refs/*.wav`) и из подключённых Datasets.

Иврит и итальянские омографы Whisper не различит (бóкер и бокéр пишутся одинаково) — их слушаем.

В конце: `/kaggle/working/chatterbox_eval/report.html` и архив `chatterbox_eval.zip`. Скачайте архив, распакуйте
и откройте `report.html`: там все записи с плеером, распознанный текст (Whisper) и CER.
""")

code(r"""
# 1. Установка. Коммит закреплён: 5de7a54 (v3 multilingual + Nano).
# Пакет тянет torch==2.6.0 и transformers==5.2.0: на Kaggle это займёт несколько минут.
!pip install -q "chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54" jiwer
# Необязательно: русская расстановка ударений, которую Chatterbox вызывает сам для language_id="ru".
!pip install -q russian-text-stresser || echo "russian-text-stresser не установился — тест 5в пропустим"
# Иврит: огласовки (никуд) через Dicta. Chatterbox вызывает Dicta() без пути к модели — это падает,
# и текст уходит без огласовок. Поэтому ставим сами и вызываем явно.
!pip install -q dicta-onnx && wget -q -nc -P /kaggle/working https://github.com/thewh1teagle/dicta-onnx/releases/download/model-files-v1.0/dicta-1.0.int8.onnx || echo "Dicta не установилась — вариант he_dicta пропустим"
# Образцы голоса Паоло и свежая версия задачи — из публичного репозитория
!rm -rf /kaggle/working/task && git clone -q --depth 1 https://github.com/vasiliad/italo-tutor-chatterbox /kaggle/working/task && ls /kaggle/working/task/refs
""")

code(r"""
# 2. Общие функции
import os, glob, time, json, re, unicodedata, gc
import numpy as np, torch, torchaudio as ta, pandas as pd

import platform
def pick_device():
    if not torch.cuda.is_available():
        return "cpu"
    cap = torch.cuda.get_device_capability(0)
    arch = f"sm_{cap[0]}{cap[1]}"
    if arch not in torch.cuda.get_arch_list():
        print(f"ВНИМАНИЕ: {torch.cuda.get_device_name(0)} ({arch}) не поддерживается этой сборкой torch "
              f"{torch.__version__} {torch.cuda.get_arch_list()} — работаем на CPU")
        return "cpu"
    return "cuda"
DEVICE = pick_device()
torch.set_num_threads(os.cpu_count())
HW = (f"{torch.cuda.get_device_name(0)}" if DEVICE == "cuda" else "CPU") + \
     f", ядер: {os.cpu_count()}, RAM: {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30:.0f} ГБ, torch {torch.__version__}"
print("DEVICE =", DEVICE, "|", HW)
QUICK = DEVICE == "cpu"   # на CPU — сокращённый набор; можно поставить False вручную

OUT = "/kaggle/working/chatterbox_eval"
os.makedirs(f"{OUT}/wav", exist_ok=True)
ROWS = []

def synth(model, section, name, text, lang, seed=0, audio_prompt=None, tag="", **kw):
    '''Генерирует одну запись, сохраняет wav и строку метаданных.'''
    torch.manual_seed(seed); np.random.seed(seed)
    dev = model.device
    if dev == "cuda":
        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    wav = model.generate(text, language_id=lang, audio_prompt_path=audio_prompt, **kw)
    if dev == "cuda":
        torch.cuda.synchronize()
    dt = time.time() - t0
    fn = f"{section}__{name}.wav".replace(" ", "_").replace("/", "_")
    ta.save(f"{OUT}/wav/{fn}", wav, model.sr)
    dur = wav.shape[-1] / model.sr
    row = dict(section=section, name=name, text=text, lang=lang, seed=seed, tag=tag,
               params=json.dumps(kw, ensure_ascii=False), file=f"wav/{fn}",
               dur_s=round(dur, 2), gen_s=round(dt, 2), rtf=round(dt / max(dur, 1e-6), 3),
               vram_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2) if dev == "cuda" else None)
    ROWS.append(row)
    print(f"[{section}] {name}: {dur:.1f}s audio, {dt:.1f}s gen, RTF {row['rtf']}")
    return wav

def save_rows():
    pd.DataFrame(ROWS).to_csv(f"{OUT}/results.csv", index=False)

def with_mark(word_grave, mark):
    '''Слово записано с грависом на ударной гласной (telèfonano). Возвращает вариант
    с нужным комбинируемым знаком: "grave" (U+0300), "acute" (U+0301) или "none".'''
    d = unicodedata.normalize("NFD", word_grave)
    if mark == "none":
        d = d.replace("̀", "").replace("́", "")
    elif mark == "acute":
        d = d.replace("̀", "́")
    return unicodedata.normalize("NFC", d)
""")

code(r"""
# 3. Загрузка v3 и проверка словаря токенайзера: видит ли модель знаки ударения
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
m3 = ChatterboxMultilingualTTS.from_pretrained(DEVICE, t3_model="v3")
print("sample rate:", m3.sr)

tok = m3.tokenizer
vocab = tok.tokenizer.get_vocab()
UNK_ID = vocab.get("[UNK]")
print("размер словаря:", len(vocab))
for ch, nm in [("̀", "U+0300 гравис"), ("́", "U+0301 острое ударение"), ("̆", "U+0306 (й)"), ("̈", "U+0308 (ё)")]:
    print(f"  {nm}: {'ЕСТЬ' if ch in vocab else 'нет'}")

def show_tokens(text, lang):
    ids = tok.encode(text, language_id=lang)
    toks = [tok.tokenizer.id_to_token(i) for i in ids]
    unk = sum(1 for i in ids if i == UNK_ID)
    print(f"{lang} {text!r}\n   -> {' | '.join(repr(t) for t in toks)}  {'<-- UNK: %d' % unk if unk else ''}")

for t in ["telefonano", "telèfonano", with_mark("telèfonano", "acute"), "perché", "città", "ancóra", "àncora"]:
    show_tokens(t, "it")
for t in ["замок", "за́мок", "замо́к", "ёлка"]:
    show_tokens(t, "ru")

# Сохраняем в отчёт
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    for ch in ["̀", "́"]:
        print(f"U+{ord(ch):04X} в словаре: {ch in vocab}")
    for t in ["telèfonano", with_mark("telèfonano", "acute"), "ancóra"]:
        show_tokens(t, "it")
    for t in ["за́мок", "замо́к"]:
        show_tokens(t, "ru")
TOKEN_REPORT = buf.getvalue()
""")

code(r"""
# 4. Итальянский A1: 12 фраз из программы Паоло, встроенный голос, v3
IT_A1 = [
    "Ciao, mi chiamo Paolo. Come ti chiami?",
    "Piacere! Sono russa, di Mosca.",
    "Vorrei un caffè e un cornetto, per favore.",
    "Quanto costa questo libro?",
    "Dov'è la stazione? È lontana da qui?",
    "C'è una farmacia vicino all'albergo?",
    "Mi piace la musica, ma non mi piacciono i film dell'orrore.",
    "Ho ventitré anni e abito a Mosca.",
    "Ieri ho mangiato la pizza con i miei amici.",
    "Scusi, a che ora parte il treno per Firenze?",
    "Mia sorella lavora in un ospedale.",
    "Domani andiamo al mare, se non piove.",
]
for i, t in enumerate(IT_A1[:4] if QUICK else IT_A1):
    synth(m3, "it_a1", f"v3_{i:02d}", t, "it", seed=i)
save_rows()
""")

code(r"""
# 5. Ударение: трудные слова (ошибки Паоло на экзамене) и пары слов с разным смыслом.
# Каждое слово: без знака / с грависом / с острым знаком; отдельно и в рамке «Dico ___ adesso.»
STRESS = [  # (форма с грависом на ударной гласной, пояснение)
    ("telèfonano", "4-й от конца"), ("parliàmo", ""), ("desìderano", "4-й от конца"),
    ("capìscono", ""), ("scrìvono", ""), ("farmacìa", ""), ("psicologìa", ""),
    ("Brìndisi", ""), ("famìglia", ""), ("sùbito", ""),
    ("àncora", "якорь"), ("ancòra", "ещё"), ("càpitano", "случаются"), ("capitàno", "капитан"),
    ("prìncipi", "принцы"), ("princìpi", "принципы"),
]
for w, note in (STRESS[:1] + STRESS[10:14] if QUICK else STRESS):
    base = with_mark(w, "none")
    for mark in ["none", "grave", "acute"]:
        form = with_mark(w, mark)
        synth(m3, "stress", f"{base}_{w}_{mark}_solo", f"{form}.", "it", seed=1, tag=note)
        synth(m3, "stress", f"{base}_{w}_{mark}_frame", f"Dico {form} adesso.", "it", seed=1, tag=note)
save_rows()
""")

code(r"""
# 5б. Итальянские омографы: выбирает ли модель слово по контексту (без знака) и слушается ли знака.
# Последняя группа — фраза, неоднозначная по-настоящему: без знака её не разберёт никто.
IT_CTX = [  # (имя, фраза без знака, та же фраза со знаком на ударной гласной)
    ("ancora_ancòra",     "Vorrei ancora un caffè.",                          "Vorrei ancòra un caffè."),
    ("ancora_àncora",     "La nave getta l'ancora in porto.",                 "La nave getta l'àncora in porto."),
    ("principi_princìpi", "I principi della fisica sono semplici.",           "I princìpi della fisica sono semplici."),
    ("principi_prìncipi", "Il re e la regina hanno due figli: sono principi.", "Il re e la regina hanno due figli: sono prìncipi."),
    ("capitano_capitàno", "Il capitano parla con i marinai.",                 "Il capitàno parla con i marinai."),
    ("capitano_càpitano", "Queste cose capitano spesso.",                     "Queste cose càpitano spesso."),
    ("subito_sùbito",     "Vieni subito qui!",                                "Vieni sùbito qui!"),
    ("subito_subìto",     "Ha subito un furto ieri sera.",                    "Ha subìto un furto ieri sera."),
]
for name, plain, marked in IT_CTX:
    synth(m3, "it_context", f"{name}_plain", plain, "it", seed=8, tag="контекст, без знака")
    synth(m3, "it_context", f"{name}_mark", marked, "it", seed=8, tag="со знаком")
for name, t in [("plain", "Ho visto i principi."), ("princes", "Ho visto i prìncipi."), ("principles", "Ho visto i princìpi.")]:
    synth(m3, "it_ambiguous", name, t, "it", seed=8)
save_rows()
""")

code(r"""
# 5в. Иврит — те же вопросы, что для итальянского:
#   базовые фразы; выбор слова по контексту без огласовок; огласовки Dicta (автомат); огласовки вручную (верные);
#   неоднозначная фраза; знак ударения ole (U+05AB), которого модель, судя по коду, при обучении не видела.
import chatterbox.models.tokenizers.tokenizer as cbtok
cbtok.add_hebrew_diacritics = lambda text: text   # огласовки подаём сами, чтобы сравнивать варианты
try:
    from dicta_onnx import Dicta
    DICTA = Dicta("/kaggle/working/dicta-1.0.int8.onnx")
except Exception as e:
    DICTA = None; print("Dicta недоступна:", e)

HE_BASIC = ["שלום, מה שלומך?", "קוראים לי פאולו.", "אני רוצה כוס קפה, בבקשה.",
            "איפה התחנה?", "כמה זה עולה?", "אני גר בתל אביב."]
for i, t in enumerate(HE_BASIC):
    synth(m3, "he_basic", f"{i:02d}", t, "he", seed=9)

HE_CTX = [  # (имя, без огласовок, огласовки вручную — верное слово)
    ("boker_morning",  "בוקר טוב!",               "בֹּקֶר טוֹב!"),
    ("boker_cowboy",   "הבוקר רכב על סוס.",       "הַבּוֹקֵר רָכַב עַל סוּס."),
    ("okhel_food",     "האוכל על השולחן.",        "הָאֹכֶל עַל הַשֻּׁלְחָן."),
    ("okhel_eats",     "הוא אוכל לחם.",           "הוּא אוֹכֵל לֶחֶם."),
    ("sefer_book",     "אני קורא ספר.",           "אֲנִי קוֹרֵא סֵפֶר."),
    ("sapar_barber",   "הספר גזר לי את השיער.",   "הַסַּפָּר גָּזַר לִי אֶת הַשֵּׂעָר."),
    ("banu_built",     "הם בנו בית חדש.",         "הֵם בָּנוּ בַּיִת חָדָשׁ."),
    ("banu_in_us",     "הוא בוטח בנו.",           "הוּא בּוֹטֵחַ בָּנוּ."),
    ("shlomekh_fem",   "שלום, מה שלומך?",         "שָׁלוֹם, מַה שְּׁלוֹמֵךְ?"),
]
for name, plain, manual in HE_CTX:
    synth(m3, "he_context", f"{name}_plain", plain, "he", seed=9, tag="без огласовок (как сейчас в Chatterbox)")
    if DICTA:
        auto = DICTA.add_diacritics(plain)
        synth(m3, "he_context", f"{name}_dicta", auto, "he", seed=9,
              tag="Dicta" + ("" if unicodedata.normalize("NFC", auto) == unicodedata.normalize("NFC", manual) else " (≠ вручную)"))
    synth(m3, "he_context", f"{name}_manual", manual, "he", seed=9, tag="огласовки вручную")

for name, t in [("plain", "הבוקר היה נחמד."), ("morning", "הַבֹּקֶר הָיָה נֶחְמָד."), ("cowboy", "הַבּוֹקֵר הָיָה נֶחְמָד.")]:
    synth(m3, "he_ambiguous", name, t, "he", seed=9)

OLE = "\u05AB"
HE_STRESS = [  # (имя, текст) — одинаковые буквы и огласовки, разница только в знаке ударения
    ("banu_plain",      "בָּנוּ."),
    ("banu_ole_first",  "בָּ" + OLE + "נוּ."),          # bánu «в нас»
    ("shalom_plain",    "שָׁלוֹם."),
    ("shalom_ole_wrong", "שָׁ" + OLE + "לוֹם."),         # нарочно неверное: шáлом — послушается ли модель?
]
for name, t in HE_STRESS:
    synth(m3, "he_stress", name, t, "he", seed=9)
save_rows()
""")

code(r"""
# 6. Двойные согласные: различимы ли pala/palla и т. п.
PAIRS = [("pala", "palla"), ("caro", "carro"), ("sete", "sette"), ("nono", "nonno"), ("papa", "papà"), ("camino", "cammino")]
for a, b in PAIRS:
    synth(m3, "geminates", f"{a}_{b}", f"{a.capitalize()}. {b.capitalize()}.", "it", seed=2)
    synth(m3, "geminates", f"{a}_{b}_sent", f"Ho detto {a}, non {b}.", "it", seed=2)
save_rows()
""")

code(r"""
# 7. Русский: без ударений, с ручными ударениями, повтор 8 раз (issue #360)
import chatterbox.models.tokenizers.tokenizer as cbtok
RU = [
    ("plain", "Сегодня мы говорим о прошедшем времени. Это совсем не сложно."),
    ("zamok_plain", "Это старый замок."),
    ("zamok_1", "Это старый за́мок."),
    ("zamok_2", "Это старый замо́к."),
    ("plachu_1", "Я пла́чу, когда слушаю эту песню."),
    ("plachu_2", "Я плачу́ за кофе."),
    ("muka_1", "Это была настоящая му́ка."),
    ("muka_2", "Купи муку́ для пиццы."),
]

# 7а. Без автоматического расстановщика (как в пакете по умолчанию)
cbtok._russian_stresser = None
_stresser_backup = cbtok.add_russian_stress
cbtok.add_russian_stress = lambda text: text
for name, t in RU:
    synth(m3, "ru", f"nostress_{name}", t, "ru", seed=3)

# 7б. С автоматическим расстановщиком, если он установлен
cbtok.add_russian_stress = _stresser_backup
try:
    from russian_text_stresser.text_stresser import RussianTextStresser  # noqa
    for name, t in RU[:2]:
        print("stresser:", cbtok.add_russian_stress(t))
        synth(m3, "ru", f"stresser_{name}", t, "ru", seed=3)
except Exception as e:
    print("russian_text_stresser недоступен:", e)
cbtok.add_russian_stress = lambda text: text  # дальше — без него, чтобы ручные ударения не перезаписывались

# 7в. Повтор одной фразы 8 раз подряд: появляется ли «английский» акцент к концу
for i in range(3 if QUICK else 8):
    synth(m3, "ru_repeat", f"{i}", RU[0][1], "ru", seed=100 + i)
save_rows()
""")

code(r"""
# 8. Смешанная фраза Паоло: русское пояснение с итальянскими словами
from chatterbox.models.s3gen import S3GEN_SR

MIX = "В прошедшем времени мы всегда говорим «ho mangiato», а не «io mangiato»."
synth(m3, "mix", "whole_ru", MIX, "ru", seed=4)

SEGMENTS = [("ru", "В прошедшем времени мы всегда говорим,"), ("it", "ho mangiato,"),
            ("ru", "а не"), ("it", "io mangiato.")]
parts, t0 = [], time.time()
for lang, seg in SEGMENTS:
    torch.manual_seed(4)
    w = m3.generate(seg, language_id=lang)
    parts += [w, torch.zeros(1, int(0.12 * m3.sr))]
wav = torch.cat(parts, dim=-1)
ta.save(f"{OUT}/wav/mix__split.wav", wav, m3.sr)
dur = wav.shape[-1] / m3.sr
ROWS.append(dict(section="mix", name="split_ru_it", text=" | ".join(s for _, s in SEGMENTS), lang="ru+it",
                 seed=4, tag="склейка", params="{}", file="wav/mix__split.wav", dur_s=round(dur, 2),
                 gen_s=round(time.time() - t0, 2), rtf=None, vram_gb=None))
save_rows()
""")

code(r"""
# 9. Клон голоса Паоло по записи из Dataset (русская речь Algenib)
refs = sorted(glob.glob("/kaggle/working/task/refs/*.wav") + glob.glob("/kaggle/input/**/*.wav", recursive=True))
print("образцы:", refs)
REF = next((r for r in refs if "vpn" in r), refs[0] if refs else None)
if REF is None:
    print("Нет образцов — пропускаем клонирование")
else:
    import librosa
    y, sr = librosa.load(REF, sr=24000)
    ref10 = f"{OUT}/wav/_ref_10s.wav"
    ta.save(ref10, torch.from_numpy(y[: 10 * sr]).unsqueeze(0), sr)
    ROWS.append(dict(section="clone", name="_reference", text=os.path.basename(REF), lang="ru", seed=0, tag="образец",
                     params="{}", file="wav/_ref_10s.wav", dur_s=10, gen_s=None, rtf=None, vram_gb=None))
    synth(m3, "clone", "ru_plain", RU[0][1], "ru", seed=5, audio_prompt=ref10)
    synth(m3, "clone", "mix_whole", MIX, "ru", seed=5, audio_prompt=ref10)
    for i in [0, 2, 6, 9]:
        for cfg in [0.5, 0.0]:
            synth(m3, "clone", f"it_{i:02d}_cfg{cfg}", IT_A1[i], "it", seed=5, audio_prompt=ref10, cfg_weight=cfg)
    for w in ["telèfonano", "àncora", "ancòra"]:
        synth(m3, "clone", f"stress_{w}", f"Dico {w} adesso.", "it", seed=5, audio_prompt=ref10, cfg_weight=0.0)
    # вернуть встроенный голос для следующих тестов
    m3 = ChatterboxMultilingualTTS.from_pretrained(DEVICE, t3_model="v3")
save_rows()
""")

code(r"""
# 10. Медленно для ученицы: параметры модели + растяжение без смены тона
import librosa
for i in [0, 2, 9]:
    for cfg, ex in [(0.5, 0.5), (0.3, 0.5), (0.3, 0.3)]:
        w = synth(m3, "slow", f"{i:02d}_cfg{cfg}_ex{ex}", IT_A1[i], "it", seed=6, cfg_weight=cfg, exaggeration=ex)
    y = librosa.effects.time_stretch(w.squeeze(0).numpy(), rate=0.8)
    fn = f"wav/slow__{i:02d}_stretch0.8.wav"
    ta.save(f"{OUT}/{fn}", torch.from_numpy(y).unsqueeze(0), m3.sr)
    ROWS.append(dict(section="slow", name=f"{i:02d}_stretch0.8", text=IT_A1[i], lang="it", seed=6, tag="librosa x0.8",
                     params='{"cfg_weight": 0.3, "exaggeration": 0.3}', file=fn, dur_s=round(len(y) / m3.sr, 2),
                     gen_s=None, rtf=None, vram_gb=None))
save_rows()
""")

code(r"""
# 11. v2 против v3 на тех же фразах и словах
del m3; gc.collect()
if DEVICE == "cuda": torch.cuda.empty_cache()
m2 = ChatterboxMultilingualTTS.from_pretrained(DEVICE, t3_model="v2")
for i, t in enumerate(IT_A1[:4] if QUICK else IT_A1):
    synth(m2, "it_a1", f"v2_{i:02d}", t, "it", seed=i)
for w, note in (STRESS[:3] if QUICK else STRESS[:10]):
    for mark in ["none", "grave"]:
        synth(m2, "stress_v2", f"{with_mark(w, 'none')}_{mark}", f"Dico {with_mark(w, mark)} adesso.", "it", seed=1, tag=note)
del m2; gc.collect()
if DEVICE == "cuda": torch.cuda.empty_cache()
m3 = ChatterboxMultilingualTTS.from_pretrained(DEVICE, t3_model="v3")
save_rows()
""")

code(r"""
# 12. Скорость на CPU (все ядра машины Kaggle)
mc = m3 if DEVICE == "cpu" else ChatterboxMultilingualTTS.from_pretrained("cpu", t3_model="v3")
synth(mc, "cpu", "short", IT_A1[3], "it", seed=7)
synth(mc, "cpu", "long", IT_A1[6], "it", seed=7)
if mc is not m3:
    del mc; gc.collect()
save_rows()

# Сколько места займёт на карте 128 ГБ: веса (кэш HF) и пакеты Python
def du(path):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs
               if not os.path.islink(os.path.join(d, f))) / 2**30
from huggingface_hub import scan_cache_dir
for repo in scan_cache_dir().repos:
    if "chatterbox" in repo.repo_id.lower():
        print(repo.repo_id, round(repo.size_on_disk / 2**30, 2), "ГБ")
        for rev in repo.revisions:
            for f in sorted(rev.files, key=lambda f: -f.size_on_disk):
                print(f"   {f.file_name}: {f.size_on_disk / 2**20:.0f} МБ")
import site
sp = site.getsitepackages()[0]
for pkg in ["torch", "transformers", "chatterbox", "librosa", "diffusers", "nvidia"]:
    p = os.path.join(sp, pkg)
    if os.path.isdir(p):
        print(f"site-packages/{pkg}: {du(p):.2f} ГБ")
""")

code(r"""
# 13. Распознавание Whisper large-v3-turbo и CER (ударение ASR не видит — его слушаем)
import jiwer
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo",
               dtype=torch.float16 if DEVICE == "cuda" else torch.float32, device=DEVICE)
LANG = {"it": "italian", "ru": "russian", "ru+it": "russian", "he": "hebrew"}

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # убираем знаки ударения
    s = s.replace("ё", "е").replace("’", "'")
    s = re.sub(r"[^\w' ]+", " ", s)
    return " ".join(s.split())

for r in ROWS:
    if r["name"] == "_reference":
        continue
    y, _ = librosa.load(f"{OUT}/{r['file']}", sr=16000)
    out = asr({"raw": y, "sampling_rate": 16000},
              generate_kwargs={"language": LANG[r["lang"]], "task": "transcribe"})
    r["asr"] = out["text"].strip()
    ref = r["text"].replace(" | ", " ")
    r["cer"] = round(jiwer.cer(norm(ref), norm(r["asr"])), 3) if norm(ref) else None
save_rows()
df = pd.DataFrame(ROWS)
print(df.groupby("section")[["cer", "rtf", "dur_s"]].mean(numeric_only=True))
""")

code(r"""
# 14. HTML-отчёт и архив
import html, shutil
TITLES = {
    "it_a1": "Итальянский A1 (v3 и v2)", "stress": "Ударение: без знака / гравис / острый (v3)",
    "stress_v2": "Ударение (v2)", "geminates": "Двойные согласные", "ru": "Русский",
    "ru_repeat": "Русский: 8 повторов подряд (issue #360)", "mix": "Смешанная фраза Паоло",
    "clone": "Клон голоса Паоло", "slow": "Медленное чтение", "cpu": "CPU",
    "it_context": "Итальянские омографы: контекст без знака / со знаком",
    "it_ambiguous": "Итальянский: неоднозначная фраза", "he_basic": "Иврит: базовые фразы",
    "he_context": "Иврит: выбор слова по контексту / Dicta / огласовки вручную",
    "he_ambiguous": "Иврит: неоднозначная фраза", "he_stress": "Иврит: знак ударения ole",
}
summary = df.groupby("section").agg(n=("name", "count"), cer=("cer", "mean"), rtf=("rtf", "mean"),
                                    vram=("vram_gb", "max")).round(3)
parts = ["<!doctype html><meta charset='utf-8'><title>Chatterbox eval</title>",
         "<style>body{font:14px system-ui;margin:16px;max-width:1200px}table{border-collapse:collapse;width:100%}"
         "td,th{border:1px solid #ccc;padding:4px;vertical-align:top}audio{width:230px}.bad{background:#fdd}"
         "pre{background:#f4f4f4;padding:8px;overflow:auto}</style>",
         "<h1>Chatterbox Multilingual: проверка для italo-tutor</h1>",
         f"<p>{html.escape(HW)}</p>",
         "<h2>Токенайзер</h2><pre>" + html.escape(TOKEN_REPORT) + "</pre>",
         "<h2>Сводка</h2>" + summary.to_html()]
for sec, g in df.groupby("section", sort=False):
    parts.append(f"<h2>{html.escape(TITLES.get(sec, sec))}</h2><table><tr><th>имя</th><th>текст</th>"
                 "<th>звук</th><th>Whisper</th><th>CER</th><th>сек / RTF</th><th>параметры</th><th>оценка на слух</th></tr>")
    for _, r in g.iterrows():
        bad = " class='bad'" if isinstance(r.get("cer"), float) and r["cer"] > 0.1 else ""
        parts.append(f"<tr{bad}><td>{html.escape(str(r['name']))}<br><small>{html.escape(str(r['tag']))}</small></td>"
                     f"<td>{html.escape(r['text'])}</td><td><audio controls preload='none' src='{r['file']}'></audio></td>"
                     f"<td>{html.escape(str(r.get('asr', '')))}</td><td>{r.get('cer', '')}</td>"
                     f"<td>{r['dur_s']} / {r['rtf']}</td><td><small>{html.escape(r['params'])}</small></td><td></td></tr>")
    parts.append("</table>")
open(f"{OUT}/report.html", "w").write("\n".join(parts))
shutil.rmtree("/kaggle/working/task", ignore_errors=True)  # чтобы копия репозитория не попала в Output
shutil.make_archive("/kaggle/working/chatterbox_eval", "zip", OUT)
print("Готово: /kaggle/working/chatterbox_eval.zip")
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
      "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
for c in nb["cells"]:
    src = c["source"]
    c["source"] = [l + "\n" for l in src.split("\n")]
    c["source"][-1] = c["source"][-1].rstrip("\n")
json.dump(nb, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
