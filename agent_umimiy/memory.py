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
MAX_MEMORY_BYTES = 10 * 1024 * 1024
_SECRET = re.compile(
    r"(?i)(?:api[_ -]?key|password|passwd|secret|token)\s*[:=]\s*\S+|"
    r"\bsk-(?:or-v1-|proj-|live-)?[A-Za-z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bBearer\s+\S+"
)


def _path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    from .config import user_dir
    return user_dir() / "memory.json"


def _read(path: Path) -> list[dict]:
    try:
        if path.stat().st_size > MAX_MEMORY_BYTES:
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("id") and item.get("fact")]


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
        json.dump(items, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def remember(fact: str, path: str | Path | None = None) -> str:
    fact = str(fact).strip()
    if not fact:
        return "Saqlanadigan ma'lumot bo'sh."
    if len(fact) > MAX_FACT_LENGTH:
        return f"Ma'lumot {MAX_FACT_LENGTH} belgidan uzun; qisqartirib yuboring."
    if _SECRET.search(fact):
        return "Parol, API kalit yoki maxfiy token xotiraga saqlanmaydi."
    path = _path(path)
    with _lock:
        items = _read(path)
        for item in items:
            if item["fact"].casefold() == fact.casefold():
                return f"Bu ma'lumot xotirada bor (ID: {item['id']})."
        if len(items) >= MAX_ITEMS:
            return f"Xotira limiti {MAX_ITEMS} ta. Avval eski yozuvlardan birini o'chiring; yangi ma'lumot kesib tashlanmadi."
        item_id = uuid.uuid4().hex[:10]
        items.append({"id": item_id, "fact": fact})
        _write(path, items)
    return f"Xotiraga saqlandi (ID: {item_id})."


def search(query: str, limit: int = 5, path: str | Path | None = None) -> str:
    path = _path(path)
    with _lock:
        items = _read(path)
    if not items:
        return "Xotirada hali ma'lumot yo'q."
    terms = {word.casefold() for word in re.findall(r"[\w'-]+", str(query)) if len(word) > 1}
    stop = {"the", "and", "for", "that", "this", "with", "from", "what", "when", "where", "which",
            "qanday", "qaysi", "haqida", "uchun", "bilan", "eslab", "qolgan", "menga", "mening"}
    terms -= stop
    ranked = []
    for item in items:
        fact = str(item["fact"])
        words = {word.casefold() for word in re.findall(r"[\w'-]+", fact) if len(word) > 1}
        score = len(terms & words)
        if query and str(query).strip().casefold() in fact.casefold():
            score += 3
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    selected = [item for _, item in ranked[:max(1, min(int(limit), 10))]] if ranked else items[-min(max(1, int(limit)), 5):]
    if not selected:
        return "Xotirada mos ma'lumot yo'q."
    return "\n".join(f"[{item['id']}] {item['fact']}" for item in selected)


def list_items(path: str | Path | None = None) -> list[dict]:
    with _lock:
        return _read(_path(path))


def forget(item_id: str, path: str | Path | None = None) -> str:
    item_id = str(item_id).strip()
    path = _path(path)
    with _lock:
        items = _read(path)
        kept = [item for item in items if str(item["id"]) != item_id]
        if len(kept) == len(items):
            return "Bu ID bilan xotira topilmadi."
        _write(path, kept)
    return "Xotiradagi ma'lumot o'chirildi."
