"""Telegram Bot ko'prigi: qo'shimcha kutubxonasiz (faqat urllib.request) Telegram orqali
kelgan xabarlarni Agent Umimiy orqali bajaradi va javob qaytaradi."""
from __future__ import annotations

import json
import threading
import urllib.request
from typing import Callable


class TelegramBridge:
    def __init__(self, ask_fn: Callable[[str], str]):
        self.ask_fn = ask_fn
        self.token = ""
        self.allowed_username = ""
        self.status = "o'chiq"
        self.error = ""
        self.bot_username = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def configure(self, token: str, allowed_username: str = "") -> dict:
        token = str(token or "").strip()
        allowed = str(allowed_username or "").strip().lstrip("@").lower()
        if token == self.token and allowed == self.allowed_username and self._thread and self._thread.is_alive():
            return self.info()
        self.stop()
        self.token = token
        self.allowed_username = allowed
        if not token:
            self.status, self.error, self.bot_username = "o'chiq", "", ""
            return self.info()
        try:
            me = self._api("getMe", {}, timeout=5)
            if not me.get("ok"):
                raise ValueError("Bot tokeni noto'g'ri")
            self.bot_username = str((me.get("result") or {}).get("username") or "bot")
            self.status, self.error = "ulangan", ""
            self._stop.clear()
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
        except Exception as exc:
            self.status, self.error, self.bot_username = "xato", str(exc)[:200], ""
        return self.info()

    def stop(self) -> None:
        self._stop.set()
        self.status = "o'chiq"

    def info(self) -> dict:
        return {
            "enabled": bool(self.token),
            "status": self.status,
            "bot_username": self.bot_username,
            "allowed_username": self.allowed_username,
            "error": self.error,
        }

    def _api(self, method: str, payload: dict, timeout: float = 25) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def _poll_loop(self) -> None:
        offset = 0
        while not self._stop.is_set():
            try:
                res = self._api("getUpdates", {"offset": offset, "timeout": 15}, timeout=20)
                for upd in res.get("result") or []:
                    offset = max(offset, int(upd.get("update_id", 0)) + 1)
                    msg = upd.get("message") or {}
                    chat_id = (msg.get("chat") or {}).get("id")
                    text = str(msg.get("text") or "").strip()
                    sender = str((msg.get("from") or {}).get("username") or "").lower()
                    if not chat_id or not text:
                        continue
                    if self.allowed_username and sender != self.allowed_username:
                        self._api("sendMessage", {"chat_id": chat_id, "text": "Ruxsat yo'q."})
                        continue
                    if text == "/start":
                        self._api(
                            "sendMessage",
                            {"chat_id": chat_id, "text": "Salom! Agent Umimiy tayyor. Savolingizni yozing."},
                        )
                        continue
                    answer = self.ask_fn(text)
                    self._api("sendMessage", {"chat_id": chat_id, "text": (answer or "(bo'sh javob)")[:4000]})
            except Exception:
                if self._stop.wait(3):
                    break
