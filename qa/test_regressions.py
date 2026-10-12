"""Phase 1 regression contracts: intentional failures document unfixed defects.
Run: .venv/bin/python -m pytest qa/test_regressions.py -q
HTTP tests default to the existing API, use QA_API_URL for the isolated API.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.api_client import AskReply, QAApiClient, QAApiError
from bot.main import NEW_CHAT, build_router

BASE = os.environ.get("QA_API_URL", "http://127.0.0.1:8000")


@pytest.mark.parametrize("name", ["malformed-xml.xlsx", "malformed-sheet.xlsx"])
def test_corrupt_xml_returns_validation_error(name):
    content = (Path(__file__).parent / "fixtures" / name).read_bytes()
    response = httpx.post(BASE + "/ingest", files={"file": (name, content)}, timeout=60)
    assert response.status_code == 422, (response.status_code, response.text)


@pytest.mark.parametrize("field", ["session_id", "question"])
def test_null_bytes_are_rejected(field):
    payload = {"question": "ID karta olish uchun nima kerak?", "session_id": "qa-null-test"}
    payload[field] += "\x00"
    response = httpx.post(BASE + "/ask", json=payload, timeout=60)
    assert response.status_code == 422, (response.status_code, response.text)


@pytest.mark.parametrize("question", ["pensiya nechpul", "ID-karta narxi"])
def test_unrelated_answer_is_not_presented_as_correct(question):
    response = httpx.post(BASE + "/ask", json={"question": question}, timeout=60)
    assert response.status_code == 200
    body = response.json()
    # No pension amount is in the supplied corpus. ID-card price must mention price/fee,
    # not the fields printed on the card. Abstention is safer than a wrong answer.
    if question == "pensiya nechpul":
        assert not body["found"], body
    else:
        assert not body["found"] or any(s in body["answer"].lower() for s in ("narx", "boj", "to'lov", "bhm")), body


def test_bot_preserves_full_answer():
    async def scenario():
        text = "x" * 4096 + " MUHIM ISTISNO"
        api = AsyncMock()
        api.ask.return_value = AskReply(found=True, answer=text, matched_question="q", score=1)
        message = AsyncMock()
        message.text = "long answer please"
        message.from_user.id = 123
        message.chat.id = 456
        await build_router(api).message.handlers[3].callback(message)
        sent = "".join(call.args[0] for call in message.answer.call_args_list)
        assert sent == text

    asyncio.run(scenario())


def test_failed_reset_does_not_claim_success():
    async def scenario():
        api = AsyncMock()
        api.reset.side_effect = QAApiError("API unavailable")
        router = build_router(api)
        message = AsyncMock()
        message.from_user.id = 123
        message.chat.id = 456
        await router.message.handlers[1].callback(message)
        assert message.answer.call_args.args[0] != NEW_CHAT

    asyncio.run(scenario())


@pytest.mark.parametrize("body", [b"not JSON", b"{}"])
def test_bot_wraps_invalid_upstream_responses(body):
    async def scenario():
        api = QAApiClient("http://api.test", 1)
        await api._http.aclose()
        api._http = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)), base_url="http://api.test"
        )
        try:
            with pytest.raises(QAApiError):
                await api.ask("pasport", "qa")
        finally:
            await api.close()

    asyncio.run(scenario())


def test_bot_does_not_call_long_valid_telegram_message_service_outage():
    async def scenario():
        api = QAApiClient(BASE, 60)
        message = AsyncMock()
        message.text = "x" * 1001
        message.from_user.id = 123
        message.chat.id = 456
        try:
            router = build_router(api)
            await router.message.handlers[3].callback(message)
            from bot.main import SERVICE_DOWN

            assert message.answer.call_args.args[0] != SERVICE_DOWN
        finally:
            await api.close()

    asyncio.run(scenario())


def test_failed_ingest_does_not_publish_changed_answer():
    from app.domain.errors import StorageUnavailableError
    from app.domain.models import QAPair, QASheet
    from tests.fakes import build_services

    services = build_services([QAPair(question="QA passport", answer="old answer")])

    def fail(_):
        raise StorageUnavailableError("Qdrant offline")

    services.index.indexed_answer_ids = fail
    with pytest.raises(StorageUnavailableError):
        services.ingestion.ingest(QASheet(pairs=[QAPair(question="QA passport", answer="new answer")], skipped=[]))
    result = services.search.ask("QA passport")
    assert result.answer == "old answer", result


def test_null_session_delete_is_rejected():
    response = httpx.delete(BASE + "/sessions/qa%00null", timeout=60)
    assert response.status_code == 422, (response.status_code, response.text)


def test_evaluation_has_a_disjoint_holdout_dataset():
    import json

    from app.domain.text import normalize

    directory = Path(__file__).resolve().parents[1] / "eval"

    def queries(path):
        found = set()
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            turns = row.get("turns", [row])
            found.update(normalize(turn["query"]) for turn in turns)
        return found

    # evaluate.main sweeps and chooses the threshold on dev.jsonl itself.
    tuning = queries(directory / "dev.jsonl")
    candidates = [path for path in directory.glob("*.jsonl") if path.name != "dev.jsonl"]
    independent = [path.name for path in candidates if queries(path) and not queries(path) & tuning]
    assert independent, "No separate query-disjoint evaluation dataset; calibration and reported evaluation reuse data"
