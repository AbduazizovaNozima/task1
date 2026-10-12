import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

from bot.api_client import QAApiClient
from bot.main import build_router

root = Path(__file__).resolve().parent
compose = [
    "docker",
    "compose",
    "-p",
    "task1_adversarial_qa",
    "-f",
    str(root / "clean-clone/docker-compose.yml"),
    "-f",
    str(root / "clean-clone/qa-isolated.yml"),
]


async def run():
    api = QAApiClient("http://127.0.0.1:18000", 3)
    result = {}
    try:
        for name, index in [("question", 3), ("new", 1)]:
            message = AsyncMock()
            message.text = "ID karta olish uchun nima kerak?"
            message.from_user.id = 321
            message.chat.id = 321
            await build_router(api).message.handlers[index].callback(message)
            result[name] = [call.args[0] for call in message.answer.call_args_list]
    finally:
        await api.close()
    (root / "evidence/bot_actual_outage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))


try:
    subprocess.run([*compose, "stop", "api"], check=True)
    asyncio.run(run())
finally:
    subprocess.run([*compose, "start", "api"], check=True)
