import pytest

from app.domain.models import QAPair, QASheet, SkippedRow
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


def test_ingest_embeds_in_batches_of_normalized_text(parts: Parts) -> None:
    make_service(parts).ingest(SHEET)

    embedder = parts[2]
    assert [len(call) for call in embedder.calls] == [2, 1]
    assert embedder.calls[0][0] == "pasport qanday olinadi?"


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
