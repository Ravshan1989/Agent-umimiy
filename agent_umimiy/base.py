from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .tools import Cancelled, Context, Toolbox


@dataclass
class Result:
    agent: str
    text: str
    ok: bool = True
    seconds: float = 0.0
    error: str = ""


class AgentError(Exception):
    pass


class Agent(ABC):
    """Har bir AI agent shu interfeysni amalga oshiradi."""

    kind = "base"
    supports_tools = False

    def __init__(self, name: str, description: str = "", **options):
        self.name = name
        self.description = description
        self.options = options

    @abstractmethod
    def _ask(self, prompt: str, history: list[dict]) -> str: ...

    def _ask_tools(self, prompt: str, history: list[dict], tb: Toolbox) -> str:
        return self._ask(prompt, history)

    def ask(self, prompt: str, history: list[dict] | None = None, ctx: Context | None = None) -> Result:
        start = time.monotonic()
        self.ctx = ctx
        history = list(history or [])
        try:
            if ctx and ctx.active and self.supports_tools and self.options.get("tools", True):
                try:
                    text = self._ask_tools(prompt, history, Toolbox(ctx, self.name))
                except AgentError as exc:
                    # model asboblarni qo'llamasa (masalan, kichik lokal model) — oddiy chatga qaytamiz
                    if "HTTP 400" not in str(exc) or "tool" not in str(exc).lower():
                        raise
                    text = self._ask(prompt, history)
            else:
                text = self._ask(prompt, history)
            return Result(self.name, text, True, time.monotonic() - start)
        except Cancelled:
            return Result(self.name, "", False, time.monotonic() - start, "To'xtatildi")
        except Exception as exc:  # agent xatosi butun tizimni to'xtatmasligi kerak
            return Result(self.name, "", False, time.monotonic() - start, str(exc))


def http_json(url: str, payload: dict, headers: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise AgentError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}") from exc
    except urllib.error.URLError as exc:
        raise AgentError(f"Ulanish xatosi: {exc.reason}") from exc
