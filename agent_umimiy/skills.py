"""Ko'nikmalar (skills): papkadagi SKILL.md — agentga qanday ishlashni o'rgatuvchi ko'rsatma.
Claude formatiga mos: ~/.claude/skills va plaginlardagi ko'nikmalar ham avtomatik topiladi."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import config

_cache: dict = {}


@dataclass
class Skill:
    name: str
    description: str
    path: Path  # SKILL.md joylashgan papka
    source: str


def parse(text: str) -> tuple[dict, str]:
    """Oddiy frontmatter (--- ... ---): `kalit: qiymat`, `>`/`|` ko'p qatorli qiymatlar."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    meta, key = {}, None
    for line in text[3:end].strip("\r\n").splitlines():
        if line[:1] in (" ", "\t") and key:
            meta[key] = (meta[key] + " " + line.strip()).strip()
        elif ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            meta[key] = "" if val in (">", "|", ">-", "|-") else val.strip("\"'")
    return meta, text[end + 4:].lstrip("\r\n")


def _roots(project: str | None) -> list[tuple[Path, str]]:
    out = []
    if project:
        out.append((Path(project) / ".claude" / "skills", "loyiha"))
    out += [(config.user_dir() / "skills", "Agent Umimiy"), (Path.home() / ".claude" / "skills", "Claude")]
    return out


def discover(project: str | None = None, ttl: float = 5.0) -> list[Skill]:
    key = project or ""
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    found: dict[str, Skill] = {}
    files = []
    for root, src in _roots(project):
        if root.is_dir():
            files += [(f, src) for f in sorted(root.glob("*/SKILL.md"))]
    plug = Path.home() / ".claude" / "plugins"
    if plug.is_dir():
        files += [(f, "Claude plagin") for f in sorted(plug.glob("**/skills/*/SKILL.md"))[:200]]
    for f, src in files:
        try:
            meta, _ = parse(f.read_text(encoding="utf-8", errors="replace")[:4000])
        except OSError:
            continue
        name = meta.get("name") or f.parent.name
        if name not in found:  # birinchi topilgan (loyiha > o'zimizniki > Claude) ustun
            found[name] = Skill(name, (meta.get("description") or "")[:400], f.parent, src)
    result = list(found.values())
    _cache[key] = (time.time(), result)
    return result


def load(name: str, project: str | None = None, file: str = "") -> str:
    sk = next((s for s in discover(project) if s.name == name), None)
    if not sk:
        raise KeyError(f"Ko'nikma topilmadi: {name}. Mavjud: {', '.join(s.name for s in discover(project)) or '—'}")
    if file:
        target = (sk.path / file).resolve()
        target.relative_to(sk.path.resolve())  # papkadan tashqariga chiqishni to'sadi (ValueError)
        return target.read_text(encoding="utf-8", errors="replace")
    _, body = parse((sk.path / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
    others = [str(p.relative_to(sk.path)) for p in sorted(sk.path.rglob("*")) if p.is_file() and p.name != "SKILL.md"][:40]
    extra = ("\n\n[Bu ko'nikma papkasidagi boshqa fayllar (use_skill(name, file=...) bilan o'qing): " + ", ".join(others) + "]") if others else ""
    return body + extra
