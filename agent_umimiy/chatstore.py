"""Suhbatlarni foydalanuvchi papkasida saqlash (dastur yopilib ochilganda tiklash uchun)."""
from __future__ import annotations

import json
import os

from . import config

MAX_CHATS, MAX_RECORDS, MAX_HISTORY = 15, 80, 40


def path():
    return config.user_dir() / "chats.json"


# Har yozuv turi uchun gui._replay talab qiladigan kalitlar
_NEED = {"user": ("text",), "agent": ("name", "text"), "act": ("agent", "kind", "text")}


def _ok_record(r) -> bool:
    return isinstance(r, dict) and r.get("k") in _NEED and all(key in r for key in _NEED[r["k"]])


def _clean(c) -> dict | None:
    """Buzilgan suhbatni tashlab yuboradi, yaroqsiz yozuvlarni olib tashlaydi."""
    if not isinstance(c, dict):
        return None
    records, history = c.get("records"), c.get("history")
    records = [r for r in records if _ok_record(r)] if isinstance(records, list) else []
    if not records:
        return None
    history = [h for h in history if isinstance(h, dict)] if isinstance(history, list) else []
    title, project = c.get("title"), c.get("project")
    return dict(c, records=records, history=history, title=title if isinstance(title, str) else "",
                project=project if isinstance(project, str) else "")


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"chats": [], "active": 0}
    if not isinstance(data, dict) or not isinstance(data.get("chats"), list):
        return {"chats": [], "active": 0}
    chats = [c for c in (_clean(c) for c in data["chats"]) if c is not None]
    active = data.get("active", 0)
    active = active if isinstance(active, int) and 0 <= active < len(chats) else 0
    return {"chats": chats, "active": active}


def save(chats: list[dict], active: int) -> None:
    # Faol indeks filtrlangan ro'yxatga moslanadi (bo'sh suhbatlar tashlanadi, eng oxirgi MAX_CHATS qoladi)
    keep = [i for i, c in enumerate(chats) if c["records"]][-MAX_CHATS:]
    new_active = keep.index(active) if active in keep else max(0, len(keep) - 1)
    chats = [dict(chats[i], records=chats[i]["records"][-MAX_RECORDS:], history=chats[i]["history"][-MAX_HISTORY:])
             for i in keep]
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"chats": chats, "active": new_active},
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
