from uuid import uuid4

import pytest

from app.domain.errors import EmptyQueryError
from app.domain.models import QAPair, VectorHit
from app.services.search import best_per_answer
from tests.fakes import build_services

PAIRS = [
    QAPair(question="Pasport qanday olinadi", answer="DXM orqali."),
    QAPair(question="Pasport almashtirish tartibi", answer="DXM orqali."),
    QAPair(question="Pasport yo'qolsa nima qilinadi", answer="Ichki ishlar organiga ariza beriladi."),
    QAPair(question="Nikoh qayerda qayd etiladi", answer="FHDYO bo'limida."),
]


def test_ask_returns_answer_and_candidates() -> None:
    result = build_services(PAIRS).search.ask("Pasport  qanday OLINADI")

    assert result.found
    assert result.answer == "DXM orqali."
    assert result.matched_question == "Pasport qanday olinadi"
    assert result.score == pytest.approx(1.0)
    assert result.candidates[0].question == "Pasport qanday olinadi"


def test_ask_reports_not_found_below_threshold() -> None:
    result = build_services(PAIRS, threshold=0.9).search.ask("ertaga ob-havo qanday")

    assert not result.found
    assert result.answer is None
    assert result.score is not None and result.score < 0.9


def test_ask_rejects_blank_query() -> None:
    with pytest.raises(EmptyQueryError):
        build_services(PAIRS).search.ask("   ")


def test_ask_ignores_uncommitted_indexed_question() -> None:
    services = build_services(PAIRS)
    services.repository.questions.clear()

    assert not services.search.ask("Pasport qanday olinadi").found


def test_ask_can_exclude_previous_answer() -> None:
    services = build_services(PAIRS)
    first = services.search.ask("pasport qanday olinadi")

    second = services.search.ask("pasport qanday olinadi", exclude_answer_id=first.answer_id)

    assert second.answer_id != first.answer_id


def test_short_ambiguous_query_asks_to_clarify() -> None:
    pairs = [QAPair(question="pasport olish", answer="A"), QAPair(question="pasport almashtirish", answer="B")]
    services = build_services(pairs, threshold=0.5, ambiguity_margin=0.05)

    result = services.search.ask("pasport")

    assert not result.found
    assert set(result.suggestions) == {"pasport olish", "pasport almashtirish"}


def test_long_query_is_never_treated_as_ambiguous() -> None:
    pairs = [QAPair(question="pasport olish", answer="A"), QAPair(question="pasport almashtirish", answer="B")]
    services = build_services(pairs, threshold=0.3, ambiguity_margin=1.0)

    assert services.search.ask("menga pasport olish kerak edi").found


def test_rank_returns_one_hit_per_answer() -> None:
    ranked = build_services(PAIRS).search.rank("pasport")

    assert len(ranked) == len({hit.answer_id for hit in ranked})


def test_best_per_answer_keeps_highest_score() -> None:
    answer = uuid4()
    low = VectorHit(question_id=uuid4(), answer_id=answer, score=0.4)
    high = VectorHit(question_id=uuid4(), answer_id=answer, score=0.9)

    assert best_per_answer([low, high]) == [high]


def test_calibrated_default_rejects_between_old_and_new_threshold() -> None:
    from app.config import Settings
    from app.domain.models import Candidate

    settings = Settings(_env_file=None)
    service = build_services(threshold=settings.match_threshold).search
    # Midpoint between the frozen baseline and dev-selected candidate, independent of query wording.
    candidate = Candidate(answer_id=uuid4(), question="generic query", answer="generic answer", score=(0.64 + 0.67) / 2)
    assert not service._decide("generic query", [candidate]).found
