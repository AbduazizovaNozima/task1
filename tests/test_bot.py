import ast
from pathlib import Path

from bot.api_client import AskReply
from bot.main import CLARIFY, NOT_FOUND, format_reply

BOT_DIR = Path(__file__).resolve().parents[1] / "bot"


def reply(found: bool, answer: str | None) -> AskReply:
    return AskReply(found=found, answer=answer, matched_question=None, score=0.9)


def test_found_answer_is_sent_as_is() -> None:
    assert format_reply(reply(True, "DXM orqali.")) == "DXM orqali."


def test_not_found_gives_friendly_message() -> None:
    assert format_reply(reply(False, None)) == NOT_FOUND


def test_ambiguous_reply_lists_suggestions() -> None:
    ambiguous = AskReply(
        found=False,
        answer=None,
        matched_question=None,
        score=0.7,
        suggestions=["Pasport olish", "Pasport almashtirish"],
    )

    assert format_reply(ambiguous) == f"{CLARIFY}\n• Pasport olish\n• Pasport almashtirish"


def test_long_answer_is_not_truncated() -> None:
    assert format_reply(reply(True, "x" * 10_000)) == "x" * 10_000


def test_bot_never_imports_the_app_package() -> None:
    for source in BOT_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("app"), source.name
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith("app") for alias in node.names), source.name


def test_handler_sends_all_answer_chunks_without_markup() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from bot.main import TELEGRAM_MESSAGE_LIMIT, build_router

    async def scenario() -> None:
        text = "* _ [ ] < > & " * 800
        api = AsyncMock()
        api.ask.return_value = reply(True, text)
        message = AsyncMock()
        message.text = "question"
        await build_router(api).message.handlers[3].callback(message)
        calls = message.answer.call_args_list
        assert "".join(call.args[0] for call in calls) == text
        assert all(0 < len(call.args[0]) <= TELEGRAM_MESSAGE_LIMIT for call in calls)
        assert all(call.kwargs["parse_mode"] is None for call in calls)

    asyncio.run(scenario())


def test_failed_reset_reports_service_unavailable() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from bot.api_client import QAApiError
    from bot.main import SERVICE_DOWN, build_router

    async def scenario() -> None:
        api = AsyncMock()
        api.reset.side_effect = QAApiError("offline")
        message = AsyncMock()
        await build_router(api).message.handlers[1].callback(message)
        message.answer.assert_awaited_once_with(SERVICE_DOWN)

    asyncio.run(scenario())


def test_bot_explains_invalid_question() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from bot.api_client import QAApiValidationError
    from bot.main import INVALID_QUESTION, build_router

    async def scenario() -> None:
        api = AsyncMock()
        api.ask.side_effect = QAApiValidationError("too long")
        message = AsyncMock()
        message.text = "x" * 1001
        await build_router(api).message.handlers[3].callback(message)
        message.answer.assert_awaited_once_with(INVALID_QUESTION)

    asyncio.run(scenario())
