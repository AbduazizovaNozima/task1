import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.api_client import AskReply, QAApiClient, QAApiError, QAApiValidationError
from bot.config import BotSettings

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
NOISY_LOGGERS = ("httpx", "aiogram.event")

HELP = (
    "Men davlat xizmatlari bo'yicha savollarga javob beraman: pasport va ID-karta, nikoh va FHDYO, "
    "haydovchilik guvohnomasi, soliq va tadbirkorlik, pensiya va nafaqalar, ta'lim va tibbiyot, "
    "harbiy xizmat, notarius va ko'chmas mulk."
)
WELCOME = "Assalomu alaykum! Savolingizni bemalol lotin yoki kirill yozuvida so'rashingiz mumkin.\n\n" + HELP
NOT_FOUND = (
    "Kechirasiz, bu savolga mos javob bazada topilmadi. "
    "Savolni boshqacharoq ifodalab ko'ring yoki /help orqali mavzularni ko'ring."
)
CLARIFY = "Savolingizni aniqlashtiring. Balki quyidagilardan birini nazarda tutgandirsiz:"
SERVICE_DOWN = "Xizmat vaqtincha ishlamayapti. Birozdan so'ng qayta urinib ko'ring."
INVALID_QUESTION = "Savolni tekshiring: bo‘sh bo‘lmagan, 1000 belgidan oshmaydigan matn yuboring."
TEXT_ONLY = "Iltimos, savolingizni matn ko'rinishida yozing."


def format_reply(reply: AskReply) -> str:
    if reply.found and reply.answer:
        return reply.answer
    if reply.suggestions:
        return "\n".join([CLARIFY, *(f"• {question}" for question in reply.suggestions)])
    return NOT_FOUND


def build_router(api: QAApiClient) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(WELCOME)

    @router.message(Command("help"))
    async def on_help(message: Message) -> None:
        await message.answer(HELP)

    @router.message(F.text)
    async def on_question(message: Message) -> None:
        try:
            reply = await api.ask(message.text or "")
        except QAApiValidationError:
            await message.answer(INVALID_QUESTION)
            return
        except QAApiError:
            logger.exception("Q&A API request failed")
            await message.answer(SERVICE_DOWN)
            return
        text = format_reply(reply)
        for offset in range(0, len(text), TELEGRAM_MESSAGE_LIMIT):
            await message.answer(text[offset : offset + TELEGRAM_MESSAGE_LIMIT], parse_mode=None)

    @router.message()
    async def on_other(message: Message) -> None:
        await message.answer(TEXT_ONLY)

    return router


async def run() -> None:
    settings = BotSettings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    bot = Bot(settings.telegram_bot_token)
    try:
        api = QAApiClient(settings.api_base_url, settings.api_timeout_seconds)
        try:
            dispatcher = Dispatcher()
            dispatcher.include_router(build_router(api))
            logger.info("Bot started, API: %s", settings.api_base_url)
            await dispatcher.start_polling(bot)
        finally:
            await api.close()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
