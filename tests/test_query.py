import pytest

from app.domain.query import expand


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Id karta qanaqa qilib olinadi", "id karta qanday olinadi"),
        ("Ид карта қанақа қилиб олинади", "id karta qanday olinadi"),
        ("ЗАГС қаерда", "zags qayerda fhdyo"),
        ("prava olish uchun ekzamen", "prava olish uchun ekzamen haydovchilik guvohnomasi imtihon"),
        ("erga tegmoqchiman prava olmayman", "erga tegmoqchiman nikoh"),
        ("pensiya olmayman nima qilay", "pensiya olmayman nima qilay"),
        ("pravaslav cherkovi", "pravaslav cherkovi"),
    ],
)
def test_normalizes_scripts_and_expands_only_nonnegated_glossary_words(query: str, expected: str) -> None:
    assert expand(query) == expected
