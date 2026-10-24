from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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

    def __init__(self, name: str, description: str = "", **options):
        self.name = name
        self.description = description
        self.options = options

    @abstractmethod
    def _ask(self, prompt: str, history: list[dict]) -> str: ...

    def ask(self, prompt: str, history: list[dict] | None = None) -> Result:
        start = time.monotonic()
        try:
            text = self._ask(prompt, history or [])
            return Result(self.name, text, True, time.monotonic() - start)
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
