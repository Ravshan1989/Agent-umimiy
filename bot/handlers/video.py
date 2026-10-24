import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from bot import texts
from bot.config import Config
from bot.downloader import TooBigError, download_video, extract_url, make_temp_dir

log = logging.getLogger(__name__)


def build_router(config: Config) -> Router:
    router = Router()

    @router.message(F.text.regexp(r"https?://"))
    async def on_link(message: Message) -> None:
        url = extract_url(message.text)
        if not url:
            return
        status = await message.answer(texts.DOWNLOADING)
        with make_temp_dir() as tmp:
            try:
                path = await download_video(url, Path(tmp), config.max_upload_mb)
                await message.answer_video(FSInputFile(path))
            except TooBigError:
                await message.answer(texts.TOO_BIG)
            except Exception:
                log.exception("Yuklashda xato: %s", url)
                await message.answer(texts.DOWNLOAD_FAILED)
        await status.delete()

    return router
