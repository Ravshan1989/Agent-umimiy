import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import texts
from bot.config import load_config
from bot.handlers import video


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    bot = Bot(config.bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(texts.START)

    dp.include_router(video.build_router(config))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
