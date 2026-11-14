from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from . import detect
from .orchestrator import Orchestrator
from .providers import build_agent

MAX_CONFIG_BYTES = 1024 * 1024
MAX_AGENTS = 16
DEFAULT = {"judge": "", "routes": {}, "agents": [], "project": "", "mcp": [], "remote": False, "server": False,
           "lang": "uz", "theme": "dark", "accent": "violet"}


def user_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "AgentUmimiy"
    try:
        path.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            path.chmod(0o700)
    except OSError:
        pass
    return path


def upload_dir() -> Path:
    """Yuklangan fayllar (telefon, veb, skrinshot) papkasi; 7 kundan eski fayllar tozalanadi."""
    d = user_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*"):
        try:
            if time.time() - old.stat().st_mtime > 7 * 86400:
                old.unlink()
        except OSError:
            pass
    return d


def config_path(path: str | None = None) -> Path:
    return Path(path) if path else user_dir() / "agents.json"


def read(path: str | None = None) -> dict:
    p = config_path(path)
    if not p.exists():
        return json.loads(json.dumps(DEFAULT))
    if p.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError("agents.json fayli 1 MB dan katta.")
    for attempt in range(2):
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))  # BOM bo'lsa ham o'qiladi
            if isinstance(data, dict):
                return {**DEFAULT, **data}
        except ValueError:
            pass
        if attempt == 0:
            time.sleep(0.2)  # boshqa jarayon ayni paytda yozayotgan bo'lishi mumkin — bir marta qayta urinamiz
    # Buzilgan fayl: dastur yiqilmasin, nusxasini saqlab standart sozlamalarni qaytaramiz
    try:
        os.replace(p, p.with_name(p.name + ".broken"))
    except OSError:
        pass
    return json.loads(json.dumps(DEFAULT))


def write(cfg: dict, path: str | None = None) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("Konfiguratsiya obyekt bo'lishi kerak.")
    p = config_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cfg, indent=2, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_CONFIG_BYTES:
        raise ValueError("Konfiguratsiya 1 MB dan katta bo'lmasligi kerak.")
    # Atomar yozish: avval yonidagi vaqtinchalik faylga, keyin os.replace (yarim yozilgan fayl qolmaydi)
    tmp = p.with_suffix(p.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
    except OSError:
        pass
    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)
    os.replace(tmp, p)


_DETECT_CACHE: tuple[float, list[dict], list[dict]] = (0.0, [], [])


def _cached_local_and_freellm(ttl: float = 30.0) -> tuple[list[dict], list[dict]]:
    global _DETECT_CACHE
    now = time.monotonic()
    if now - _DETECT_CACHE[0] < ttl:
        return [dict(x) for x in _DETECT_CACHE[1]], [dict(x) for x in _DETECT_CACHE[2]]
    loc = detect.local_servers()
    gw = detect.freellmapi()
    _DETECT_CACHE = (now, loc, gw)
    return [dict(x) for x in loc], [dict(x) for x in gw]


def build(cfg: dict) -> Orchestrator:
    raw_agents = cfg.get("agents", [])
    if not isinstance(raw_agents, list) or any(not isinstance(a, dict) for a in raw_agents):
        raise ValueError("agents sozlamasi ro'yxat bo'lishi va har bir agent obyekt bo'lishi kerak.")
    enabled = [dict(a) for a in raw_agents if a.get("enabled", True)]
    # Ollama'ga yuklangan yangi model va lokal FreeLLMAPI ilova qayta ochilganda
    # avtomatik qo'shiladi. Qo'lda sozlangan model takrorlanmaydi.
    # Faqat echo agentlardan iborat test sozlamalariga tashqi serverlar qo'shilmaydi.
    if not enabled or not all(a.get("type") == "echo" for a in enabled):
        loc_list, gw_list = _cached_local_and_freellm()
        known_ollama = {str(a.get("model", "")) for a in enabled if a.get("type") == "ollama"}
        for detected in loc_list:
            if detected.get("type") != "ollama" or detected.get("model") in known_ollama:
                continue
            model = str(detected["model"])
            low = model.lower()
            if "coder" in low:
                detected["description"] = "Lokal model — dasturlash, kod tahlili va xatolarni tuzatish"
            elif "vl" in low or "vision" in low or "llava" in low:
                detected["description"] = "Lokal model — rasm, skrinshot va hujjatlarni tahlil qilish"
            enabled.append(detected)
            known_ollama.add(model)
        known_names = {str(a.get("name", "")) for a in enabled}
        for gw in gw_list:
            if gw.get("name") not in known_names and gw.get("api_key"):
                enabled.append(gw)
                known_names.add(str(gw["name"]))
    if len(enabled) > MAX_AGENTS:
        raise ValueError(f"Ko'pi bilan {MAX_AGENTS} ta agent sozlash mumkin.")
    agents = [build_agent(a) for a in enabled]
    if not agents:
        agents = [build_agent({"name": "demo", "type": "echo", "description": "Demo (agent sozlanmagan)"})]
    names = {a.name for a in agents}
    judge = cfg.get("judge") if cfg.get("judge") in names else agents[0].name
    return Orchestrator(agents, judge=judge, routes=cfg.get("routes"))


def load(path: str | None = None) -> Orchestrator:
    return build(read(path))
