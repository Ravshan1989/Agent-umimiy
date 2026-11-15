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


# Har yozuv turi uchun gui._replay talab qiladigan kalitlar
_NEED = {"user": ("text",), "agent": ("name", "text"), "act": ("agent", "kind", "text")}


def _ok_record(r) -> bool:
    return isinstance(r, dict) and r.get("k") in _NEED and all(key in r for key in _NEED[r["k"]])


def _safe_chats_and_active(chats: list, active: int) -> tuple[list[dict], int]:
    """Sanitize chats and preserve the selected chat when invalid entries are discarded."""
    safe = []
    selected = None
    start = max(0, len(chats) - MAX_CHATS)
    for original_index, chat in enumerate(chats[start:], start=start):
        if not isinstance(chat, dict):
            continue
        records = chat.get("records", [])
        history = chat.get("history", [])
        if not isinstance(records, list) or not isinstance(history, list) or not records:
            continue
        item = _clip(chat)
        item["records"] = [_clip(r) for r in records[-MAX_RECORDS:] if _ok_record(r)]
        item["history"] = [_clip(h) for h in history[-MAX_HISTORY:] if isinstance(h, dict)]
        if not item["records"]:
            continue
        for key in ("title", "project"):
            if not isinstance(item.get(key), str):
                item[key] = ""
        if original_index == active:
            selected = len(safe)
        safe.append(item)
    if not safe:
        return [], 0
    if selected is None:
        selected = min(max(active - start, 0), len(safe) - 1)
    return safe, selected


def _safe_chats(chats: list) -> list[dict]:
    return _safe_chats_and_active(chats, 0)[0]


def load() -> dict:
    empty = {"chats": [], "active": 0}
    try:
        p = path()
        if not p.is_file() or p.stat().st_size > MAX_CHATSTORE_BYTES:
            return empty
        data = json.loads(p.read_text(encoding="utf-8-sig"))  # BOM bo'lsa ham o'qiladi
        if not isinstance(data, dict) or not isinstance(data.get("chats"), list):
            return empty
        active = data.get("active", 0)
        if not isinstance(active, int) or isinstance(active, bool):
            active = 0
        chats, active = _safe_chats_and_active(data["chats"], active)
        return {"chats": chats, "active": active}
    except (OSError, ValueError, TypeError, RecursionError):
        return empty


def save(chats: list[dict], active: int) -> None:
    try:
        if not isinstance(active, int) or isinstance(active, bool):
            active = 0
        safe, active = _safe_chats_and_active(chats, active)
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
