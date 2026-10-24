import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    max_upload_mb: int = 50  # Telegram Bot API yuklash chegarasi


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan.")
    return Config(bot_token=token)
