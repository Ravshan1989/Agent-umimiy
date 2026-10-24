"""Suhbatlarni foydalanuvchi papkasida saqlash (dastur yopilib ochilganda tiklash uchun)."""
from __future__ import annotations

import json
import os

from . import config

MAX_CHATS, MAX_RECORDS, MAX_HISTORY = 15, 80, 40


def path():
    return config.user_dir() / "chats.json"


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("chats"), list) else {"chats": [], "active": 0}
    except (OSError, ValueError):
        return {"chats": [], "active": 0}


def save(chats: list[dict], active: int) -> None:
    chats = [dict(c, records=c["records"][-MAX_RECORDS:], history=c["history"][-MAX_HISTORY:])
             for c in chats if c["records"]][-MAX_CHATS:]
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"chats": chats, "active": min(active, max(0, len(chats) - 1))},
                                  ensure_ascii=False), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        os.replace(tmp, p)
    except OSError:
        pass


def clear() -> None:
    try:
        path().unlink()
    except OSError:
        pass
