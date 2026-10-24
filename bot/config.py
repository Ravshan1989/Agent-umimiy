import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    max_upload_mb: int = 50  # Telegram Bot API yuklash chegarasi
    anthropic_api_key: str = ""  # ixtiyoriy: anime bo'lmagan kino/seriallarni rasmdan topish uchun
    claude_model: str = "claude-haiku-5-5"


def load_config() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan.")
    return Config(
        bot_token=token,
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        claude_model=os.environ.get("CLAUDE_MODEL", "").strip() or Config.claude_model,
    )
