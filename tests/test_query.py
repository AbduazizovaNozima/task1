import pytest

from app.domain.query import expand, to_latin, word_count


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "man erga tegmoqchiman. necha yosh bolishim kerak?",
            "man erga tegmoqchiman. necha yosh bo'lishim kerak? nikoh",
        ),
        ("Ман эрга тегмоқчиман", "man erga tegmoqchiman nikoh"),
        ("Id karta qanaqa qilib olinadi", "id karta qanday olinadi"),
        ("Ид карта қанақа қилиб олинади", "id karta qanday olinadi"),
        ("prava olish uchun ekzamen", "prava olish uchun ekzamen haydovchilik guvohnomasi imtihon"),
        ("ЗАГС қаерда", "zags qayerda fhdyo"),
        ("malumotlarni qayerdan olaman", "ma'lumotlarni qayerdan olaman"),
        ("pasport qanday olinadi", "pasport qanday olinadi"),
    ],
)
def test_expand(query: str, expected: str) -> None:
    assert expand(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("erga tegmoqchiman prava olmayman", "erga tegmoqchiman nikoh"),
        ("3 oydan beri oylik olmayman", "3 oydan beri oylik olmayman"),
        ("pensiya olmayman nima qilay", "pensiya olmayman nima qilay"),
        ("ID karta kerak emas, pasport kerak", "id karta kerak emas, pasport kerak"),
    ],
)
def test_negation_removes_only_glossary_terms(query: str, expected: str) -> None:
    assert expand(query) == expected


def test_glossary_does_not_fire_inside_other_words() -> None:
    assert expand("pravaslav cherkovi") == "pravaslav cherkovi"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("қаерда", "qayerda"), ("ер", "yer"), ("тайёр", "tayyor"), ("ўқиш", "o'qish"), ("ғалаба", "g'alaba")],
)
def test_to_latin(text: str, expected: str) -> None:
    assert to_latin(text) == expected


def test_word_count_ignores_extra_spaces() -> None:
    assert word_count("  pensiya   nechpul ") == 2
