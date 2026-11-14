from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .tools import Cancelled, Context, Toolbox, describe_agent


@dataclass
class Result:
    agent: str
    text: str
    ok: bool = True
    seconds: float = 0.0
    error: str = ""


class AgentError(Exception):
    def __init__(self, *args, status: int | None = None):
        super().__init__(*args)
        self.status = status  # HTTP xato kodi (bo'lsa)


class Agent(ABC):
    """Har bir AI agent shu interfeysni amalga oshiradi."""

    kind = "base"
    supports_tools = False

    def __init__(self, name: str, description: str = "", **options):
        self.name = name
        self.description = description
        self.options = options
        self.ctx: Context | None = None
        self._files: list = []

    @abstractmethod
    def _ask(self, prompt: str, history: list[dict]) -> str: ...

    def _ask_tools(self, prompt: str, history: list[dict], tb: Toolbox) -> str:
        return self._ask(prompt, history)

    def _on_text(self, text: str) -> None:
        """Oqimli javobning navbatdagi bo'lagi: to'xtatish tekshiriladi va matn hodisa sifatida uzatiladi."""
        ctx = self.ctx
        if ctx and ctx.cancel.is_set():
            raise Cancelled()
        if ctx and ctx.emit:
            ctx.emit(self.name, "delta", text)

    def ask(self, prompt: str, history: list[dict] | None = None, ctx: Context | None = None, files=None) -> Result:
        start = time.monotonic()
        self.ctx, self._files = ctx, list(files or [])
        history = list(history or [])
        plain = prompt
        if ctx and ctx.roster and self.kind != "echo":  # asbobsiz yo'lda agent o'z muhitini shu orqali biladi
            plain = (f"[Context: you are the agent '{self.name}' inside the desktop app Agent Umimiy, which combines these "
                     "agents:\n" + "\n".join(describe_agent(a) for a in ctx.roster) +
                     "\nIf asked which agents exist, list all of them, not only yourself.]\n\n" + prompt)
        try:
            if ctx and ctx.active and self.supports_tools and self.options.get("tools", True):
                try:
                    text = self._ask_tools(prompt, history, Toolbox(ctx, self.name))
                except AgentError as exc:
                    # model asboblarni qo'llamasa (masalan, kichik lokal model) — oddiy chatga qaytamiz
                    if exc.status not in (400, 404, 422) and not str(exc).startswith(("HTTP 400", "HTTP 404", "HTTP 422")):
                        raise
                    text = self._ask(plain, history)
            else:
                text = self._ask(plain, history)
            return Result(self.name, text, True, time.monotonic() - start)
        except Cancelled:
            return Result(self.name, "", False, time.monotonic() - start, "To'xtatildi")
        except Exception as exc:  # agent xatosi butun tizimni to'xtatmasligi kerak
            return Result(self.name, "", False, time.monotonic() - start, str(exc))

