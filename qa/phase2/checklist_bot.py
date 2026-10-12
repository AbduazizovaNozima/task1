import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetMe, SendMessage
from aiogram.types import Message, Update, User

from bot.api_client import AskReply, QAApiClient
from bot.main import build_router

OUT = Path(__file__).resolve().parent


class CaptureSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent = []

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, GetMe):
            return User(id=123456, is_bot=True, first_name="QA", username="qa_test_bot")
        if isinstance(method, SendMessage):
            self.sent.append({"chat_id": method.chat_id, "text": method.text, "parse_mode": str(method.parse_mode)})
            return Message(
                message_id=len(self.sent), date=0, chat={"id": method.chat_id, "type": "private"}, text=method.text
            )
        raise AssertionError(type(method))

    async def stream_content(self, *args, **kwargs):
        yield b""


def update(number, payload, user=9001, edited=False):
    message = {
        "message_id": number,
        "date": 1700000000,
        "chat": {"id": user, "type": "private"},
        "from": {"id": user, "is_bot": False, "first_name": "QA"},
        **payload,
    }
    return Update.model_validate({"update_id": number, "edited_message" if edited else "message": message})


async def main():
    session = CaptureSession()
    bot = Bot("123456:" + "a" * 35, session=session)
    api = AsyncMock()
    api.ask.return_value = AskReply(found=True, answer="* _ [ ] < > &", matched_question="q", score=1)
    dp = Dispatcher()
    dp.include_router(build_router(api))
    cases = [
        ("start", {"text": "/start"}),
        ("help", {"text": "/help"}),
        ("plain", {"text": "question"}),
        ("photo", {"photo": [{"file_id": "p", "file_unique_id": "p", "width": 10, "height": 10}]}),
        (
            "sticker",
            {
                "sticker": {
                    "file_id": "s",
                    "file_unique_id": "s",
                    "type": "regular",
                    "width": 10,
                    "height": 10,
                    "is_animated": False,
                    "is_video": False,
                }
            },
        ),
        ("voice", {"voice": {"file_id": "v", "file_unique_id": "v", "duration": 1}}),
        ("file", {"document": {"file_id": "d", "file_unique_id": "d", "file_name": "test.xlsx"}}),
        (
            "forwarded",
            {
                "text": "forwarded question",
                "forward_origin": {
                    "type": "user",
                    "date": 1700000000,
                    "sender_user": {"id": 555, "is_bot": False, "first_name": "Original"},
                },
            },
        ),
    ]
    results = []
    for i, (name, payload) in enumerate(cases, 1):
        session.sent.clear()
        await dp.feed_update(bot, update(i, payload))
        results.append({"case": name, "sent": list(session.sent)})
    session.sent.clear()
    await dp.feed_update(bot, update(20, {"text": "edited question"}, edited=True))
    results.append({"case": "edited", "sent": list(session.sent)})
    session.sent.clear()
    await asyncio.gather(
        *(dp.feed_update(bot, update(30 + i, {"text": f"question {i}"}, user=9100 + i)) for i in range(10))
    )
    results.append(
        {
            "case": "ten_users",
            "sent": list(session.sent),
            "api_calls": [str(call) for call in api.ask.call_args_list[-10:]],
        }
    )
    api.ask.return_value = AskReply(found=True, answer="x" * 10000, matched_question="q", score=1)
    session.sent.clear()
    await dp.feed_update(bot, update(50, {"text": "long answer"}))
    results.append(
        {
            "case": "long_answer",
            "chunk_sizes": [len(x["text"]) for x in session.sent],
            "preserved": "".join(x["text"] for x in session.sent) == "x" * 10000,
        }
    )
    await bot.session.close()
    # Exercise the actual HTTP client timeout translation, with outgoing Telegram requests still captured.
    for name, error in [
        ("API_down", httpx.ConnectError("connection refused")),
        ("API_timeout", httpx.ReadTimeout("timed out")),
    ]:
        client = QAApiClient("http://qa.test", 0.1)
        await client._http.aclose()

        def fail(request, error=error):
            raise error

        client._http = httpx.AsyncClient(base_url="http://qa.test", transport=httpx.MockTransport(fail))
        dp2 = Dispatcher()
        dp2.include_router(build_router(client))
        session.sent.clear()
        start = time.monotonic()
        await dp2.feed_update(bot, update(60, {"text": "question"}))
        results.append(
            {
                "case": name,
                "seconds": time.monotonic() - start,
                "sent": list(session.sent),
                "transport": "injected HTTPX connection/read-timeout error",
            }
        )
        await client.close()
    (OUT / "checklist_bot.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
