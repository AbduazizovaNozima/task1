import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.api_client import AskReply, QAApiClient, QAApiError
from bot.config import BotSettings

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
NOISY_LOGGERS = ("httpx", "aiogram.event")

HELP = (
    "Men davlat xizmatlari bo'yicha savollarga javob beraman: pasport va ID-karta, nikoh va FHDYO, "
    "haydovchilik guvohnomasi, soliq va tadbirkorlik, pensiya va nafaqalar, ta'lim va tibbiyot, "
    "harbiy xizmat, notarius va ko'chmas mulk.\n\n"
    "Masalan:\n• ID karta olish uchun nima kerak?\n• Nikoh yoshi necha yosh?\n"
    "• Pensiyani kartaga o'tkazsa bo'ladimi?\n\n"
    "Lotin yoki kirill yozuvida yozishingiz mumkin. Oldingi savolingizni eslab qolaman, "
    'masalan "muddati-chi?" deb davom ettirishingiz mumkin. Yangi mavzu: /new'
)
WELCOME = "Assalomu alaykum! Savolingizni o'z so'zlaringiz bilan yozing.\n\n" + HELP
NEW_CHAT = "Yangi suhbat boshlandi. Savolingizni yozing."
NOT_FOUND = (
    "Kechirasiz, bu savolga mos javob bazada topilmadi. "
    "Savolni boshqacharoq ifodalab ko'ring yoki /help orqali mavzularni ko'ring."
)
CLARIFY = "Savolingizni aniqlashtiring. Balki quyidagilardan birini nazarda tutgandirsiz:"
SERVICE_DOWN = "Xizmat vaqtincha ishlamayapti. Birozdan so'ng qayta urinib ko'ring."
TEXT_ONLY = "Iltimos, savolingizni matn ko'rinishida yozing."


def format_reply(reply: AskReply) -> str:
    if reply.found and reply.answer:
        return reply.answer[:TELEGRAM_MESSAGE_LIMIT]
    if reply.suggestions:
        return "\n".join([CLARIFY, *(f"• {question}" for question in reply.suggestions)])[:TELEGRAM_MESSAGE_LIMIT]
    return NOT_FOUND


def session_id(message: Message) -> str:
    user_id = message.from_user.id if message.from_user else message.chat.id
    return f"telegram-{message.chat.id}-{user_id}"


def build_router(api: QAApiClient) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def on_start(message: Message) -> None:
        await _reset(message, WELCOME)

    @router.message(Command("new"))
    async def on_new(message: Message) -> None:
        await _reset(message, NEW_CHAT)

    @router.message(Command("help"))
    async def on_help(message: Message) -> None:
        await message.answer(HELP)

    @router.message(F.text)
    async def on_question(message: Message) -> None:
        try:
            reply = await api.ask(message.text or "", session_id(message))
        except QAApiError:
            logger.exception("Q&A API request failed")
            await message.answer(SERVICE_DOWN)
            return
        await message.answer(format_reply(reply))

    async def _reset(message: Message, text: str) -> None:
        try:
            await api.reset(session_id(message))
        except QAApiError:
            logger.exception("Q&A API reset failed")
        await message.answer(text)

    @router.message()
    async def on_other(message: Message) -> None:
        await message.answer(TEXT_ONLY)

    return router


async def run() -> None:
    settings = BotSettings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
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
