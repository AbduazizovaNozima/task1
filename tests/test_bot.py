import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from aiogram import Bot
from aiogram.types import Message

from bot.api_client import AskReply, QAApiClient, QAApiError, QAApiValidationError
from bot.main import INVALID_QUESTION, NOT_FOUND, SERVICE_DOWN, TELEGRAM_MESSAGE_LIMIT, build_router


def deliver(monkeypatch: pytest.MonkeyPatch, api: QAApiClient) -> list[tuple[str, str | None]]:
    sent: list[tuple[str, str | None]] = []

    async def capture(message: Message, text: str, parse_mode: str | None = None) -> Message:
        sent.append((text, parse_mode))
        return message

    monkeypatch.setattr(Message, "answer", capture)
    message = Message.model_validate(
        {"message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"}, "text": "Savol"}
    )
    asyncio.run(build_router(api).message.trigger(message, bot=Mock(spec=Bot)))
    return sent


@pytest.mark.parametrize("answer", ["DXM orqali.", None])
def test_question_routes_to_api_and_delivers_answer_or_not_found(
    monkeypatch: pytest.MonkeyPatch, answer: str | None
) -> None:
    api = AsyncMock(spec=QAApiClient)
    api.ask.return_value = AskReply(found=answer is not None, answer=answer, matched_question=None, score=0.9)
    assert deliver(monkeypatch, api) == [(answer or NOT_FOUND, None)]
    api.ask.assert_awaited_once_with("Savol")


def test_long_answer_is_delivered_completely_as_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "* _ [ ] < > & " * 800
    api = AsyncMock(spec=QAApiClient)
    api.ask.return_value = AskReply(found=True, answer=text, matched_question=None, score=0.9)
    chunks = deliver(monkeypatch, api)
    assert "".join(text for text, _ in chunks) == text
    assert all(0 < len(text) <= TELEGRAM_MESSAGE_LIMIT and mode is None for text, mode in chunks)


@pytest.mark.parametrize(
    "error,expected", [(QAApiError("offline"), SERVICE_DOWN), (QAApiValidationError("invalid"), INVALID_QUESTION)]
)
def test_api_errors_produce_an_actionable_bot_message(
    monkeypatch: pytest.MonkeyPatch, error: QAApiError, expected: str
) -> None:
    api = AsyncMock(spec=QAApiClient)
    api.ask.side_effect = error
    assert deliver(monkeypatch, api) == [(expected, None)]


@pytest.mark.parametrize(
    "status,body,error",
    [
        (200, b"not JSON", QAApiError),
        (200, b"{}", QAApiError),
        (503, b"offline", QAApiError),
        (422, b"invalid", QAApiValidationError),
    ],
)
def test_client_translates_invalid_responses_and_http_errors(
    monkeypatch: pytest.MonkeyPatch, status: int, body: bytes, error: type[QAApiError]
) -> None:
    async def respond(client: httpx.AsyncClient, request: httpx.Request, **kwargs: object) -> httpx.Response:
        return httpx.Response(status, content=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", respond)

    async def scenario() -> None:
        api = QAApiClient("http://api.test", 1)
        try:
            with pytest.raises(error):
                await api.ask("Savol")
        finally:
            await api.close()

    asyncio.run(scenario())
