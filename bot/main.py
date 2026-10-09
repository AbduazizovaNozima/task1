import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.api_client import AskReply, QAApiClient, QAApiError
from bot.config import BotSettings

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096

WELCOME = "Assalomu alaykum! Savolingizni o'z so'zlaringiz bilan yozing, men bazadan eng mos javobni topib beraman."
NOT_FOUND = "Kechirasiz, bu savolga mos javob bazada topilmadi. Savolni boshqacharoq ifodalab ko'ring."
SERVICE_DOWN = "Xizmat vaqtincha ishlamayapti. Birozdan so'ng qayta urinib ko'ring."
TEXT_ONLY = "Iltimos, savolingizni matn ko'rinishida yozing."


def format_reply(reply: AskReply) -> str:
    if not reply.found or not reply.answer:
        return NOT_FOUND
    return reply.answer[:TELEGRAM_MESSAGE_LIMIT]


def build_router(api: QAApiClient) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(WELCOME)

    @router.message(F.text)
    async def on_question(message: Message) -> None:
        try:
            reply = await api.ask(message.text or "")
        except QAApiError:
            logger.exception("Q&A API request failed")
            await message.answer(SERVICE_DOWN)
            return
        await message.answer(format_reply(reply))

    @router.message()
    async def on_other(message: Message) -> None:
        await message.answer(TEXT_ONLY)

    return router


async def run() -> None:
    settings = BotSettings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    api = QAApiClient(settings.api_base_url, settings.api_timeout_seconds)
    bot = Bot(settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(api))
    try:
        logger.info("Bot started, API: %s", settings.api_base_url)
        await dispatcher.start_polling(bot)
    finally:
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
