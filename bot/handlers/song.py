import logging
import re
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import texts
from bot.config import Config
from bot.downloader import make_temp_dir
from bot.songs import button_label, download_audio, search_songs

log = logging.getLogger(__name__)
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def build_router(config: Config) -> Router:
    router = Router()

    # Havola va buyruqlar bu yerga tushmaydi: ular boshqa router larda
    @router.message(F.text & ~F.text.startswith("/") & ~F.text.regexp(r"https?://"))
    async def on_text(message: Message) -> None:
        status = await message.answer(texts.SONG_SEARCHING)
        try:
            results = await search_songs(message.text.strip())
        except Exception:
            log.exception("Qidiruvda xato")
            results = []
        await status.delete()
        if not results:
            await message.answer(texts.SONG_NOT_FOUND)
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=button_label(s), callback_data=f"song:{s.video_id}")]
                for s in results
            ]
        )
        await message.answer(texts.SONG_PICK, reply_markup=keyboard)

    @router.callback_query(F.data.startswith("song:"))
    async def on_pick(callback: CallbackQuery) -> None:
        video_id = callback.data.split(":", 1)[1]
        await callback.answer()
        if not VIDEO_ID_RE.match(video_id) or callback.message is None:
            return
        status = await callback.message.answer(texts.SONG_DOWNLOADING)
        with make_temp_dir() as tmp:
            try:
                path = await download_audio(video_id, Path(tmp), config.max_upload_mb)
                await callback.message.answer_audio(FSInputFile(path))
            except Exception:
                log.exception("Qo'shiq yuklashda xato: %s", video_id)
                await callback.message.answer(texts.SONG_FAILED)
        await status.delete()

    return router
