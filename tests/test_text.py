import pytest

from app.domain.text import normalize, stable_id


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("O‘zbekiston", "o'zbekiston"),
        ("oʻqish  va\tgʼalaba", "o'qish va g'alaba"),
        ("Ma`lumot  ", "ma'lumot"),
        ("  ПАСПОРТ   олиш ", "паспорт олиш"),
        ("Как получить паспорт?", "как получить паспорт?"),
        ("", ""),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_stable_id_ignores_case_spaces_and_apostrophe_variants() -> None:
    assert stable_id("Oʻzbekiston  pasporti") == stable_id("o'zbekiston pasporti")


def test_stable_id_differs_for_different_text() -> None:
    assert stable_id("pasport") != stable_id("viza")
