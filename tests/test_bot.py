import ast
from pathlib import Path

from bot.api_client import AskReply
from bot.main import NOT_FOUND, TELEGRAM_MESSAGE_LIMIT, format_reply

BOT_DIR = Path(__file__).resolve().parents[1] / "bot"


def reply(found: bool, answer: str | None) -> AskReply:
    return AskReply(found=found, answer=answer, matched_question=None, score=0.9)


def test_found_answer_is_sent_as_is() -> None:
    assert format_reply(reply(True, "DXM orqali.")) == "DXM orqali."


def test_not_found_gives_friendly_message() -> None:
    assert format_reply(reply(False, None)) == NOT_FOUND


def test_long_answer_fits_telegram_limit() -> None:
    assert len(format_reply(reply(True, "x" * 10_000))) == TELEGRAM_MESSAGE_LIMIT


def test_bot_never_imports_the_app_package() -> None:
    for source in BOT_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("app"), source.name
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith("app") for alias in node.names), source.name
