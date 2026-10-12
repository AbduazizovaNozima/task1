import re

from app.domain.text import normalize

CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "j",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "x",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sh",
        "ъ": "'",
        "ь": "",
        "ы": "i",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ў": "o'",
        "қ": "q",
        "ғ": "g'",
        "ҳ": "h",
    }
)
YE_SOUND = re.compile(r"\bе|(?<=[аеёиоуэюяўъ])е")

COLLOQUIAL: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(rf"\b(?:{pattern})"), standard)
    for pattern, standard in (
        (r"qanaqa(?: qilib)?\b", "qanday"),
        (r"nechpul\b|nechi pul\b", "necha pul"),
        (r"malumot", "ma'lumot"),
        (r"bo?ladi\b", "bo'ladi"),
        (r"bolish", "bo'lish"),
        (r"togri", "to'g'ri"),
        (r"ozgar", "o'zgar"),
    )
)

NEGATION = r"olmayman|olmoqchi emasman|kerak emas|kerakmas|emas"
SYNONYMS: tuple[tuple[re.Pattern[str], re.Pattern[str], str], ...] = tuple(
    (
        re.compile(rf"\b(?:{pattern})\b"),
        re.compile(rf"\b(?:{pattern})\s+(?:{NEGATION})\b"),
        canonical,
    )
    for pattern, canonical in (
        (r"erga teg\w*|turmushga chiq\w*|uylan\w*", "nikoh"),
        (r"prava(?:m|mni|ni|si|ga|lar)?", "haydovchilik guvohnomasi"),
        (r"zags\w*", "fhdyo"),
        (r"pinfl", "jshshir"),
        (r"rodd?om\w*", "tug'ruqxona"),
        (r"l'?gota\w*", "imtiyoz"),
        (r"otpusk\w*", "ta'til"),
        (r"dekret\w*", "tug'ruq ta'tili"),
        (r"propiska\w*", "yashash joyi bo'yicha ro'yxatga olish"),
        (r"voy?enkomat\w*", "mudofaa ishlari bo'limi"),
        (r"spravka\w*", "ma'lumotnoma"),
        (r"dokument(?:lar|lari|larni|ni)?", "hujjatlar"),
        (r"ekzamen\w*|imtixon\w*", "imtihon"),
    )
)


def to_latin(text: str) -> str:
    return YE_SOUND.sub("ye", text).translate(CYRILLIC_TO_LATIN)


def prepare(query: str) -> str:
    text = to_latin(normalize(query))
    for pattern, standard in COLLOQUIAL:
        text = pattern.sub(standard, text)
    return text


def expand(query: str) -> str:
    text = prepare(query)
    additions = []
    for term, negated, canonical in SYNONYMS:
        text = negated.sub(" ", text)
        if term.search(text):
            additions.append(canonical)
    return " ".join([*text.split(), *additions])


def word_count(query: str) -> int:
    return len(normalize(query).split())
