from uuid import uuid4

import pytest

from app.domain.errors import DataInconsistencyError, EmptyQueryError
from app.domain.models import QAPair, QASheet, VectorHit
from app.services.ingestion import IngestionService
from app.services.search import SearchService, best_per_answer
from tests.fakes import FakeEmbedder, InMemoryIndex, InMemoryRepository

PAIRS = [
    QAPair(question="Pasport qanday olinadi", answer="DXM orqali."),
    QAPair(question="Pasport almashtirish tartibi", answer="DXM orqali."),
    QAPair(question="Nikoh qayerda qayd etiladi", answer="FHDYO bo'limida."),
]


def build(threshold: float = 0.5) -> tuple[SearchService, InMemoryRepository]:
    repository, index, embedder = InMemoryRepository(), InMemoryIndex(), FakeEmbedder()
    IngestionService(repository, index, embedder, batch_size=8).ingest(QASheet(pairs=PAIRS, skipped=[]))
    return SearchService(embedder, index, repository, threshold=threshold, candidates=10), repository


def test_ask_returns_answer_for_close_question() -> None:
    result = build()[0].ask("Pasport  qanday OLINADI")

    assert result.found
    assert result.answer == "DXM orqali."
    assert result.matched_question == "Pasport qanday olinadi"
    assert result.score == pytest.approx(1.0)


def test_ask_reports_not_found_below_threshold() -> None:
    result = build(threshold=0.9)[0].ask("ertaga ob-havo qanday")

    assert not result.found
    assert result.answer is None
    assert result.matched_question is None
    assert result.score is not None and result.score < 0.9


def test_ask_rejects_blank_query() -> None:
    with pytest.raises(EmptyQueryError):
        build()[0].ask("   ")


def test_ask_fails_loudly_when_database_lacks_indexed_question() -> None:
    service, repository = build()
    repository.questions.clear()

    with pytest.raises(DataInconsistencyError):
        service.ask("Pasport qanday olinadi")


def test_rank_returns_one_hit_per_answer() -> None:
    ranked = build()[0].rank("pasport")

    assert len(ranked) == len({hit.answer_id for hit in ranked}) == 2


def test_best_per_answer_keeps_highest_score() -> None:
    answer = uuid4()
    low = VectorHit(question_id=uuid4(), answer_id=answer, score=0.4)
    high = VectorHit(question_id=uuid4(), answer_id=answer, score=0.9)

    assert best_per_answer([low, high]) == [high]
