"""Suhbatlarni foydalanuvchi papkasida saqlash (dastur yopilib ochilganda tiklash uchun)."""
from __future__ import annotations

import json
import os

from . import config

MAX_CHATS, MAX_RECORDS, MAX_HISTORY = 15, 80, 40
MAX_CHATSTORE_BYTES = 50 * 1024 * 1024
MAX_TEXT_FIELD = 10_000


def path():
    return config.user_dir() / "chats.json"


def _clip(value, depth: int = 0):
    if depth > 8:
        return None
    if isinstance(value, str):
        return value[-MAX_TEXT_FIELD:]
    if isinstance(value, dict):
        return {str(k)[:100]: _clip(v, depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, list):
        return [_clip(v, depth + 1) for v in value[:100]]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)[:MAX_TEXT_FIELD]


def _safe_chats(chats: list) -> list[dict]:
    safe = []
    for chat in chats[-MAX_CHATS:]:
        if not isinstance(chat, dict):
            continue
        records = chat.get("records", [])
        history = chat.get("history", [])
        if not isinstance(records, list) or not isinstance(history, list):
            continue
        if not records:
            continue
        item = _clip(chat)
        item["records"] = [_clip(r) for r in records[-MAX_RECORDS:] if isinstance(r, dict)]
        item["history"] = [_clip(h) for h in history[-MAX_HISTORY:] if isinstance(h, dict)]
        safe.append(item)
    return safe


def load() -> dict:
    empty = {"chats": [], "active": 0}
    try:
        p = path()
        if not p.is_file() or p.stat().st_size > MAX_CHATSTORE_BYTES:
            return empty
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("chats"), list):
            return empty
        chats = _safe_chats(data["chats"])
        active = data.get("active", 0)
        if not isinstance(active, int):
            active = 0
        return {"chats": chats, "active": min(max(active, 0), max(0, len(chats) - 1))}
    except (OSError, ValueError, TypeError, RecursionError):
        return empty


def save(chats: list[dict], active: int) -> None:
    try:
        safe = _safe_chats(chats)
        if not isinstance(active, int):
            active = 0
        payload = json.dumps({"chats": safe, "active": min(max(active, 0), max(0, len(safe) - 1))},
                             ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_CHATSTORE_BYTES:
            raise ValueError("Suhbatlar fayli 50 MB dan katta.")
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, p)
    except (OSError, ValueError, TypeError):
        pass


def clear() -> None:
    try:
        path().unlink()
    except OSError:
        pass
