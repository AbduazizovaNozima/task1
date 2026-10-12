from collections.abc import Sequence

import pytest

from app.domain.models import QAPair, QASheet, Question, SkippedRow
from app.services.ingestion import IngestionService
from tests.fakes import FakeEmbedder, InMemoryIndex, InMemoryRepository

Parts = tuple[InMemoryRepository, InMemoryIndex, FakeEmbedder]

SHEET = QASheet(
    pairs=[
        QAPair(question="Pasport qanday olinadi?", answer="DXM orqali."),
        QAPair(question="Pasportni qayerdan olaman?", answer="DXM orqali."),
        QAPair(question="Nikoh qayerda qayd etiladi?", answer="FHDYO bo'limida."),
    ],
    skipped=[SkippedRow(row=5, reason="empty answer")],
)


@pytest.fixture
def parts() -> Parts:
    return InMemoryRepository(), InMemoryIndex(), FakeEmbedder()


def make_service(parts: Parts) -> IngestionService:
    repository, index, embedder = parts
    return IngestionService(repository, index, embedder, batch_size=2)


def test_ingest_deduplicates_answers_and_reports_counts(parts: Parts) -> None:
    report = make_service(parts).ingest(SHEET)

    assert report.model_dump() == {
        "rows_read": 4,
        "rows_skipped": 1,
        "answers": 2,
        "questions": 3,
        "newly_indexed": 3,
    }


def test_reingest_creates_no_duplicates_and_skips_unchanged(parts: Parts) -> None:
    service = make_service(parts)
    service.ingest(SHEET)
    report = service.ingest(SHEET)

    repository, index, _ = parts
    assert report.newly_indexed == 0
    assert len(repository.questions) == len(index.points) == 3
    assert len(repository.answers) == 2


def test_reingest_reindexes_question_whose_answer_changed(parts: Parts) -> None:
    service = make_service(parts)
    service.ingest(SHEET)
    changed = QASheet(pairs=[QAPair(question="Pasport qanday olinadi?", answer="Faqat onlayn.")], skipped=[])

    assert service.ingest(changed).newly_indexed == 1


def test_failed_vector_write_rolls_back_sql_state(parts: Parts, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.domain.errors import StorageUnavailableError

    service = make_service(parts)
    service.ingest(SHEET)
    repository, index, _ = parts
    before = repository.questions.copy(), repository.answers.copy()

    def fail(*args: object) -> None:
        raise StorageUnavailableError("vector write failed")

    monkeypatch.setattr(index, "upsert", fail)
    changed = QASheet(pairs=[QAPair(question="Pasport qanday olinadi?", answer="Changed answer")], skipped=[])
    with pytest.raises(StorageUnavailableError):
        service.ingest(changed)
    assert (repository.questions, repository.answers) == before


def test_partial_vector_write_does_not_publish_uncommitted_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.domain.errors import StorageUnavailableError
    from tests.fakes import build_services

    services = build_services([QAPair(question="passport renewal", answer="Committed answer")], batch_size=1)
    original = services.index.upsert
    calls = 0

    def write_then_fail(questions: Sequence[Question], vectors: Sequence[Sequence[float]]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise StorageUnavailableError("second vector batch failed")
        original(questions, vectors)

    monkeypatch.setattr(services.index, "upsert", write_then_fail)
    sheet = QASheet(
        pairs=[
            QAPair(question="orphan record", answer="Uncommitted"),
            QAPair(question="passport renewal", answer="Changed"),
        ],
        skipped=[],
    )
    with pytest.raises(StorageUnavailableError):
        services.ingestion.ingest(sheet)
    assert not services.search.ask("orphan record").found
    assert services.search.ask("passport renewal").answer == "Committed answer"
