"""Veb-server ma'lumotlari (SQLite): foydalanuvchilar, seanslar, suhbatlar va xabarlar.

Parollar scrypt bilan xeshlanadi, seans kalitlarining faqat SHA-256 xeshi saqlanadi.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

SESSION_DAYS = 30
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # adashtiradigan 0/O, 1/I harflarsiz
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, salt BLOB NOT NULL, hash BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '', history TEXT NOT NULL DEFAULT '[]', updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_chat ON records(chat_id, id);
"""


class StoreError(Exception):
    pass


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path | str):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.db.execute(sql, args)

    def _all(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    # ---- taklif kodi ----
    def invite(self) -> str:
        """Ro'yxatdan o'tish uchun taklif kodi (birinchi chaqiruvda yaratiladi)."""
        rows = self._all("SELECT value FROM meta WHERE key = 'invite'")
        return rows[0][0] if rows else self.new_invite()

    def new_invite(self) -> str:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        self._run("INSERT INTO meta (key, value) VALUES ('invite', ?) "
                  "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (code,))
        return code

    # ---- foydalanuvchilar ----
    def add_user(self, name: str, password: str) -> int:
        name = name.strip()
        if not 2 <= len(name) <= 32:
            raise StoreError("Ism 2 dan 32 gacha belgidan iborat bo'lsin.")
        if len(password) < 8:
            raise StoreError("Parol kamida 8 belgidan iborat bo'lsin.")
        salt = secrets.token_bytes(16)
        try:
            return self._run("INSERT INTO users (name, salt, hash) VALUES (?, ?, ?)",
                             (name, salt, _hash(password, salt))).lastrowid
        except sqlite3.IntegrityError:
            raise StoreError("Bu ism band. Boshqa ism tanlang.")

    def check_user(self, name: str, password: str) -> int | None:
        rows = self._all("SELECT id, salt, hash FROM users WHERE name = ?", (name.strip(),))
        if rows and hmac.compare_digest(_hash(password, rows[0][1]), rows[0][2]):
            return rows[0][0]
        return None

    def users(self) -> list[str]:
        return [r[0] for r in self._all("SELECT name FROM users ORDER BY name")]

    def remove_user(self, name: str) -> bool:
        return self._run("DELETE FROM users WHERE name = ?", (name.strip(),)).rowcount > 0

    # ---- seanslar ----
    def new_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._run("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        self._run("INSERT INTO sessions (token, user_id, expires) VALUES (?, ?, ?)",
                  (_digest(token), user_id, time.time() + SESSION_DAYS * 86400))
        return token

    def session_user(self, token: str) -> tuple[int, str] | None:
        rows = self._all("SELECT u.id, u.name FROM sessions s JOIN users u ON u.id = s.user_id "
                         "WHERE s.token = ? AND s.expires > ?", (_digest(token), time.time()))
        return rows[0] if rows else None

    def drop_session(self, token: str) -> None:
        self._run("DELETE FROM sessions WHERE token = ?", (_digest(token),))

    # ---- suhbatlar ----
    def chats(self, user_id: int) -> list[dict]:
        return [{"id": i, "title": t} for i, t in
                self._all("SELECT id, title FROM chats WHERE user_id = ? ORDER BY updated DESC", (user_id,))]

    def new_chat(self, user_id: int) -> int:
        return self._run("INSERT INTO chats (user_id, updated) VALUES (?, ?)", (user_id, time.time())).lastrowid

    def owns(self, user_id: int, chat_id: int) -> bool:
        return bool(self._all("SELECT 1 FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)))

    def delete_chat(self, chat_id: int) -> None:
        self._run("DELETE FROM chats WHERE id = ?", (chat_id,))

    def title(self, chat_id: int) -> str:
        return self._all("SELECT title FROM chats WHERE id = ?", (chat_id,))[0][0]

    def set_title(self, chat_id: int, title: str) -> None:
        self._run("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))

    def history(self, chat_id: int) -> list[dict]:
        return json.loads(self._all("SELECT history FROM chats WHERE id = ?", (chat_id,))[0][0])

    def set_history(self, chat_id: int, history: list[dict]) -> None:
        self._run("UPDATE chats SET history = ?, updated = ? WHERE id = ?",
                  (json.dumps(history, ensure_ascii=False), time.time(), chat_id))

    def add_record(self, chat_id: int, record: dict) -> None:
        self._run("INSERT INTO records (chat_id, body) VALUES (?, ?)", (chat_id, json.dumps(record, ensure_ascii=False)))

    def records(self, chat_id: int) -> list[dict]:
        return [json.loads(r[0]) for r in self._all("SELECT body FROM records WHERE chat_id = ? ORDER BY id", (chat_id,))]
