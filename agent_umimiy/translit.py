"""O'zbek lotin va kirill alifbolari o'rtasida aniq konvertatsiya."""
from __future__ import annotations

import re

APOSTROPHES = ("'", "‘", "’", "`", "ʼ", "ʻ")

_LAT_MULTI = [
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("yo'", "йў"), ("Yo'", "Йў"), ("YO'", "ЙЎ"),
    ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
    ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
    ("ye", "е"), ("Ye", "Е"), ("YE", "Е"),
    ("o'", "ў"), ("O'", "Ў"),
    ("g'", "ғ"), ("G'", "Ғ"),
]

_LAT_SINGLE = str.maketrans({
    "a": "а", "b": "б", "d": "д", "e": "э", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "'": "ъ",
    "A": "А", "B": "Б", "D": "Д", "E": "Э", "F": "Ф", "G": "Г", "H": "Ҳ",
    "I": "И", "J": "Ж", "K": "К", "L": "Л", "M": "М", "N": "Н", "O": "О",
    "P": "П", "Q": "Қ", "R": "Р", "S": "С", "T": "Т", "U": "У", "V": "В",
    "X": "Х", "Y": "Й", "Z": "З",
})

_CYR_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "ъ": "'", "ы": "i",
    "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o‘", "қ": "q", "ғ": "g‘", "ҳ": "h",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "J", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
    "Ф": "F", "Х": "X", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Ъ": "'", "Ы": "I",
    "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya", "Ў": "O‘", "Қ": "Q", "Ғ": "G‘", "Ҳ": "H",
}


def to_cyrillic(text: str) -> str:
    norm = str(text or "")
    for ap in APOSTROPHES:
        norm = norm.replace(ap, "'")
    # So'z o'rtasidagi 'e' harfi kirillda 'е' bo'ladi, so'z boshida esa 'э'
    norm = re.sub(r"(?<=[A-Za-z'])e", "е", norm)
    norm = re.sub(r"(?<=[A-Za-z'])E", "Е", norm)
    for src, dst in _LAT_MULTI:
        norm = norm.replace(src, dst)
    return norm.translate(_LAT_SINGLE)


def to_latin(text: str) -> str:
    src = str(text or "")
    # So'z boshidagi va unlidan keyingi Е/е -> Ye/ye
    src = re.sub(r"(^|[\s(\[\"'«аоуэияёюеўАОУЭИЯЁЮЕЎ])е", r"\1ye", src)
    src = re.sub(r"(^|[\s(\[\"'«аоуэияёюеўАОУЭИЯЁЮЕЎ])Е", r"\1Ye", src)
    return "".join(_CYR_MAP.get(ch, ch) for ch in src)


def convert(text: str, target: str = "auto") -> str:
    """Matnni lotin yoki kirillga o'giradi (`target`: 'cyr', 'lat' yoki 'auto')."""
    if target == "cyr":
        return to_cyrillic(text)
    if target == "lat":
        return to_latin(text)
    cyr_count = len(re.findall(r"[а-яА-ЯёЁўқғҳЎҚҒҲ]", text or ""))
    lat_count = len(re.findall(r"[a-zA-Z]", text or ""))
    return to_latin(text) if cyr_count > lat_count else to_cyrillic(text)
