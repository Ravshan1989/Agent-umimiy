from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .orchestrator import Orchestrator
from .providers import build_agent

DEFAULT = {"judge": "", "routes": {}, "agents": []}


def user_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "AgentUmimiy"


def config_path(path: str | None = None) -> Path:
    return Path(path) if path else user_dir() / "agents.json"


def read(path: str | None = None) -> dict:
    p = config_path(path)
    if p.exists():
        return {**DEFAULT, **json.loads(p.read_text(encoding="utf-8"))}
    return json.loads(json.dumps(DEFAULT))


def write(cfg: dict, path: str | None = None) -> None:
    p = config_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        p.chmod(0o600)  # API kalitlar bor
    except OSError:
        pass


def build(cfg: dict) -> Orchestrator:
    agents = [build_agent(a) for a in cfg.get("agents", []) if a.get("enabled", True)]
    if not agents:
        agents = [build_agent({"name": "demo", "type": "echo", "description": "Demo (agent sozlanmagan)"})]
    names = {a.name for a in agents}
    judge = cfg.get("judge") if cfg.get("judge") in names else agents[0].name
    return Orchestrator(agents, judge=judge, routes=cfg.get("routes"))


def load(path: str | None = None) -> Orchestrator:
    return build(read(path))
