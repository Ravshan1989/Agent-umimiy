import logging
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message

from bot import texts
from bot.config import Config
from bot.movies import find_movie, format_match

log = logging.getLogger(__name__)


def build_router(config: Config) -> Router:
    router = Router()

    @router.message(F.photo)
    async def on_photo(message: Message, bot: Bot) -> None:
        status = await message.answer(texts.MOVIE_SEARCHING)
        buf = BytesIO()
        try:
            await bot.download(message.photo[-1], destination=buf)
            match = await find_movie(buf.getvalue(), config.anthropic_api_key, config.claude_model)
        except Exception:
            log.exception("Kino qidirishda xato")
            await status.delete()
            await message.answer(texts.MOVIE_FAILED)
            return
        await status.delete()
        if match:
            await message.answer(format_match(match), parse_mode=ParseMode.HTML)
        else:
            await message.answer(texts.MOVIE_NOT_FOUND)

    return router
