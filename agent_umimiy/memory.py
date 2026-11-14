"""User-controlled, local-only persistent memory for the assistant."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

_lock = threading.RLock()
MAX_ITEMS = 500
MAX_FACT_LENGTH = 1000
MAX_FILE_BYTES = 1024 * 1024
_SECRET = re.compile(
    r"(?i)(?:api[_ -]?key|password|passwd|secret|token)\s*[:=]\s*\S+|"
    r"\bsk-(?:or-v1-|proj-|live-)?[A-Za-z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bBearer\s+\S+"
)


def _path() -> Path:
    from .config import user_dir
    return user_dir() / "memory.json"


class MemoryUnreadable(Exception):
    """Xotira fayli bor, lekin o'qib/tahlil qilib bo'lmadi — ustiga yozish ma'lumotni o'chirib yuboradi."""


_UNREADABLE = ("Xotira fayli ({path}) o'qilmadi yoki buzilgan, shuning uchun unga yozilmadi "
               "(ma'lumot o'chib ketmasligi uchun). Zaxira nusxa: {backup}. Faylni tuzating yoki o'chiring.")


def _read(path: Path, strict: bool = False) -> list[dict]:
    """Xotirani o'qiydi. `strict` bo'lsa, mavjud lekin buzilgan fayl uchun MemoryUnreadable ko'tariladi."""
    if not path.exists():
        return []
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("xotira fayli 1 MB dan katta")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list):
            raise ValueError("xotira ro'yxat emas")
    except (OSError, ValueError) as exc:  # JSONDecodeError va UnicodeDecodeError ham ValueError
        if strict:
            raise MemoryUnreadable(str(exc)) from exc
        return []
    return [item for item in data if isinstance(item, dict) and item.get("id") and item.get("fact")]


def _backup(path: Path) -> str:
    """Buzilgan faylning nusxasini saqlaydi (bir marta); nusxa yo'lini qaytaradi."""
    backup = path.with_name(path.name + ".bad")
    try:
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
    except OSError:
        return "saqlanmadi"
    return str(backup)


def _limit(value, default: int = 5) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _write(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
    except (AttributeError, OSError):
        pass
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(items[-MAX_ITEMS:], fh, ensure_ascii=False, indent=2)
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def remember(fact: str) -> str:
    fact = str(fact).strip()
    if not fact:
        return "Saqlanadigan ma'lumot bo'sh."
    if len(fact) > MAX_FACT_LENGTH:
        return f"Ma'lumot {MAX_FACT_LENGTH} belgidan uzun; qisqartirib yuboring."
    if _SECRET.search(fact):
        return "Parol, API kalit yoki maxfiy token xotiraga saqlanmaydi."
    path = _path()
    with _lock:
        try:
            items = _read(path, strict=True)
        except MemoryUnreadable:
            return _UNREADABLE.format(path=path, backup=_backup(path))
        for item in items:
            if item["fact"].casefold() == fact.casefold():
                return f"Bu ma'lumot xotirada bor (ID: {item['id']})."
        item_id = uuid.uuid4().hex[:10]
        items.append({"id": item_id, "fact": fact})
        _write(path, items)
    return f"Xotiraga saqlandi (ID: {item_id})."


def search(query: str, limit: int = 5) -> str:
    path = _path()
    with _lock:
        items = _read(path)
    if not items:
        return "Xotirada hali ma'lumot yo'q."
    query = str(query or "").strip()
    terms = {word.casefold() for word in re.findall(r"[\w'-]+", query) if len(word) > 1}
    stop = {"the", "and", "for", "that", "this", "with", "from", "what", "when", "where", "which",
            "qanday", "qaysi", "haqida", "uchun", "bilan", "eslab", "qolgan", "menga", "mening"}
    terms -= stop
    ranked = []
    for item in items:
        fact = str(item["fact"])
        words = {word.casefold() for word in re.findall(r"[\w'-]+", fact) if len(word) > 1}
        score = len(terms & words)
        if query and query.casefold() in fact.casefold():
            score += 3
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    limit = _limit(limit)
    if ranked:
        selected = [item for _, item in ranked[:max(1, min(limit, 10))]]
    elif not query:  # bo'sh so'rov: oxirgi yozuvlar ko'rsatiladi
        selected = items[-min(max(1, limit), 5):]
    else:
        selected = []
    if not selected:
        return "Xotirada mos ma'lumot yo'q."
    return "\n".join(f"[{item['id']}] {item['fact']}" for item in selected)


def forget(item_id: str) -> str:
    item_id = str(item_id).strip()
    path = _path()
    with _lock:
        try:
            items = _read(path, strict=True)
        except MemoryUnreadable:
            return _UNREADABLE.format(path=path, backup=_backup(path))
        kept = [item for item in items if str(item["id"]) != item_id]
        if len(kept) == len(items):
            return "Bu ID bilan xotira topilmadi."
        _write(path, kept)
    return "Xotiradagi ma'lumot o'chirildi."