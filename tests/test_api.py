import logging
import re
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_search, get_settings
from app.api.main import create_app
from app.config import Settings
from app.container import Container
from app.domain.errors import StorageUnavailableError
from app.domain.models import QAPair, VectorHit
from tests.fakes import build_services, xlsx


def make_client(check_fails: bool = False) -> TestClient:
    services = build_services()

    def check() -> None:
        if check_fails:
            raise StorageUnavailableError("PostgreSQL bilan aloqa yo'q.")

    container = Container(
        search=services.search,
        ingestion=services.ingestion,
        check=check,
        warm_up=lambda: None,
        close=lambda: None,
    )
    return TestClient(create_app(Settings(max_upload_mb=1), container_factory=lambda _: container))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with make_client() as test_client:
        yield test_client


def upload(client: TestClient, content: bytes, name: str = "qa.xlsx") -> dict[str, object]:
    response = client.post("/ingest", files={"file": (name, content)})
    return {"status": response.status_code, **response.json()}


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_health_reports_unavailable_storage() -> None:
    with make_client(check_fails=True) as client:
        response = client.get("/health")

    assert response.status_code == 503


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


@pytest.mark.parametrize("question", ["x\x00", "x\n", "x\t", "x\x1f", "x\x7f", "x\x85", "x\u202e", "x" * 1001])
def test_ask_rejects_control_characters_and_overlength_input(client: TestClient, question: str) -> None:
    response = client.post("/ask", json={"question": question})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "question"]


def test_model_warmup_failure_closes_the_container() -> None:
    from unittest.mock import Mock

    services = build_services()
    close = Mock()
    container = Container(
        search=services.search,
        ingestion=services.ingestion,
        check=lambda: None,
        warm_up=Mock(side_effect=RuntimeError("model unavailable")),
        close=close,
    )
    with (
        pytest.raises(RuntimeError, match="model unavailable"),
        TestClient(create_app(Settings(_env_file=None), container_factory=lambda _: container)),
    ):
        pass
    close.assert_called_once_with()


def test_ask_log_format_and_toggle(
    client: TestClient, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    services = build_services(
        [
            QAPair(question="id karta\u2028" + "x" * 150, answer="ID-karta\n" + "a" * 100),
            QAPair(question="Other", answer="B"),
        ],
        threshold=0.67,
        ambiguity_margin=0.02,
    )
    questions = list(services.repository.questions.values())
    index_search = Mock()
    monkeypatch.setattr(services.index, "search", index_search)
    settings = Settings(_env_file=None, log_top_k=1)
    assert isinstance(client.app, FastAPI)
    client.app.dependency_overrides[get_search] = lambda: services.search
    client.app.dependency_overrides[get_settings] = lambda: settings
    caplog.set_level(logging.INFO, logger="app.api.routes")

    cases = [
        ("id karta\u2028" + "x" * 210, [0.77549, 0.7], True, "0.775", "+0.105", "accepted"),
        ("unknown", [0.66949, 0.65], False, "0.669", "-0.001", "below_threshold"),
        ("short", [0.68949, 0.68], False, "0.689", "+0.019", "ambiguous"),
        ("unknown", [], False, "null", "null", "no_candidates"),
    ]
    for question, scores, found, score, margin, reason in cases:
        index_search.return_value = [
            VectorHit(question_id=q.id, answer_id=q.answer_id, score=value)
            for q, value in zip(questions, scores, strict=False)
        ]
        caplog.clear()
        response = client.post("/ask", json={"question": question})
        assert response.status_code == 200
        assert response.json()["found"] is found
        request_id = response.headers["X-Request-ID"]
        assert re.fullmatch(r"[0-9a-f]{8}", request_id)
        logged_question = f'id karta {"x" * 191}' if found else question
        expected = [f'ask request_id={request_id} question="{logged_question}"']
        if scores:
            expected.append(
                f"candidate request_id={request_id} rank=1 score={score} answer_id={questions[0].answer_id} "
                f'matched_question="id karta {"x" * 111}"'
            )
        chosen_rank = "1" if found else "null"
        answer = f'ID-karta {"a" * 71}' if found else ""
        expected.append(
            f"decision request_id={request_id} found={str(found).lower()} chosen_rank={chosen_rank} "
            f'score={score} threshold=0.670 margin_to_threshold={margin} reason={reason} answer="{answer}"'
        )
        assert [record.getMessage() for record in caplog.records if record.name == "app.api.routes"] == expected
        index_search.assert_called_once()
        index_search.reset_mock()

    caplog.clear()
    settings.log_questions = False
    assert client.post("/ask", json={"question": "private"}).status_code == 200
    assert not [record for record in caplog.records if record.name == "app.api.routes"]
