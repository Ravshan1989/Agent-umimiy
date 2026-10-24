from __future__ import annotations

import json
from pathlib import Path

from .orchestrator import Orchestrator
from .providers import build_agent

SEARCH = [Path("agents.json"), Path.home() / ".agent-umimiy" / "agents.json"]

DEFAULT = {
    "judge": "echo",
    "agents": [{"name": "echo", "type": "echo", "description": "Demo agent"}],
}


def load(path: str | None = None) -> Orchestrator:
    cfg = DEFAULT
    for p in [Path(path)] if path else SEARCH:
        if p.exists():
            cfg = json.loads(p.read_text(encoding="utf-8"))
            break
    return Orchestrator(
        [build_agent(a) for a in cfg["agents"]],
        judge=cfg.get("judge"),
        routes=cfg.get("routes"),
    )
