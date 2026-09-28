"""Общие преобразования входов для адаптеров моделей."""
import re


def with_word_ipa(item, fmt, key="ipa_word"):
    """Фраза, где проверяемое слово заменено на IPA в синтаксисе модели: fmt(ipa) -> строка."""
    word, ipa = item["inputs"][key]
    text, n = re.subn(rf"(?<!\w){re.escape(word)}(?!\w)", fmt(ipa), item["inputs"]["plain"], count=1)
    assert n == 1, (item["id"], word)
    return text


LANG_NAME = {"it": "Italian", "ru": "Russian", "he": "Hebrew"}


def affricates(ipa):
    """tʃ dʒ ts dz → однознаковые ʧ ʤ ʦ ʣ (как в словаре Kokoro/misaki)."""
    for a, b in [("tʃ", "ʧ"), ("dʒ", "ʤ"), ("ts", "ʦ"), ("dz", "ʣ")]:
        ipa = ipa.replace(a, b)
    return ipa
