import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.main import create_app
from app.config import Settings
from app.container import Container
from app.services.ingestion import IngestionService
from app.services.search import SearchService
from tests.fakes import FakeEmbedder, InMemoryIndex, InMemoryRepository


@pytest.fixture
def client() -> Iterator[TestClient]:
    repository, index, embedder = InMemoryRepository(), InMemoryIndex(), FakeEmbedder()
    container = Container(
        search=SearchService(embedder, index, repository, threshold=0.6, candidates=5),
        ingestion=IngestionService(repository, index, embedder, batch_size=4),
        close=lambda: None,
    )
    app = create_app(Settings(max_upload_mb=1), container_factory=lambda _: container)
    with TestClient(app) as test_client:
        yield test_client


def xlsx(rows: list[list[str | None]]) -> bytes:
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def upload(client: TestClient, content: bytes, name: str = "qa.xlsx") -> dict[str, object]:
    response = client.post("/ingest", files={"file": (name, content)})
    return {"status": response.status_code, **response.json()}


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_then_ask_finds_answer(client: TestClient) -> None:
    content = xlsx([["question", "answer"], ["Pasport qanday olinadi", "DXM orqali."], [None, "yetim javob"]])

    assert upload(client, content) == {
        "status": 200,
        "rows_read": 2,
        "rows_skipped": 1,
        "answers": 1,
        "questions": 1,
        "newly_indexed": 1,
    }
    answer = client.post("/ask", json={"question": "pasport qanday olinadi"}).json()
    assert answer["found"] is True
    assert answer["answer"] == "DXM orqali."
    assert answer["matched_question"] == "Pasport qanday olinadi"


def test_ask_returns_explicit_not_found(client: TestClient) -> None:
    upload(client, xlsx([["question", "answer"], ["Pasport qanday olinadi", "DXM orqali."]]))

    body = client.post("/ask", json={"question": "bugungi futbol natijasi"}).json()

    assert body["found"] is False
    assert body["answer"] is None


@pytest.mark.parametrize("question", ["", "   "])
def test_ask_rejects_empty_question(client: TestClient, question: str) -> None:
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_ingest_rejects_missing_columns(client: TestClient) -> None:
    result = upload(client, xlsx([["savol", "javob"], ["a", "b"]]))

    assert result["status"] == 422
    assert "question" in str(result["detail"])


def test_ingest_rejects_non_xlsx(client: TestClient) -> None:
    assert upload(client, b"plain text", name="qa.txt")["status"] == 422
    assert upload(client, b"plain text", name="qa.xlsx")["status"] == 422


def test_ingest_rejects_too_large_file(client: TestClient) -> None:
    assert upload(client, b"x" * (1024 * 1024 + 1))["status"] == 422
