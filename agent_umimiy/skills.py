"""Ko'nikmalar (skills): papkadagi SKILL.md — agentga qanday ishlashni o'rgatuvchi ko'rsatma.
Claude formatiga mos: ~/.claude/skills va plaginlardagi ko'nikmalar ham avtomatik topiladi."""
from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from . import config

MAX_SKILLS = 200
MAX_SKILL_BYTES = 1024 * 1024
MAX_SCAN_FILES = 500
_cache: dict = {}


def _read_limited(path: Path) -> str:
    if path.stat().st_size > MAX_SKILL_BYTES:
        raise ValueError("Ko'nikma fayli 1 MB dan katta.")
    with path.open("rb") as fh:
        raw = fh.read(MAX_SKILL_BYTES + 1)
    if len(raw) > MAX_SKILL_BYTES:
        raise ValueError("Ko'nikma fayli 1 MB dan katta.")
    return raw.decode("utf-8", errors="replace")


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
            remaining = MAX_SKILLS - len(files)
            if remaining <= 0:
                break
            files += [(f, src, root) for f in islice(sorted(root.glob("*/SKILL.md")), remaining)]
    plug = Path.home() / ".claude" / "plugins"
    if plug.is_dir() and len(files) < MAX_SKILLS:
        files += [(f, "Claude plagin", plug) for f in islice(plug.glob("**/skills/*/SKILL.md"), MAX_SKILLS - len(files))]
    for f, src, root in files:
        try:
            base = root.resolve()
            folder = f.parent.resolve()
            folder.relative_to(base)
            resolved = f.resolve()
            resolved.relative_to(folder)
            with resolved.open("rb") as fh:
                meta, _ = parse(fh.read(4000).decode("utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        name = meta.get("name") or f.parent.name
        if name not in found:  # birinchi topilgan (loyiha > o'zimizniki > Claude) ustun
            found[name] = Skill(name, (meta.get("description") or "")[:400], f.parent, src)
    result = list(found.values())
    if len(_cache) >= 64:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.time(), result)
    return result


def load(name: str, project: str | None = None, file: str = "") -> str:
    sk = next((s for s in discover(project) if s.name == name), None)
    if not sk:
        raise KeyError(f"Ko'nikma topilmadi: {name}. Mavjud: {', '.join(s.name for s in discover(project)) or '—'}")
    if file:
        target = (sk.path / file).resolve()
        target.relative_to(sk.path.resolve())  # papkadan tashqariga chiqishni to'sadi (ValueError)
        return _read_limited(target)
    skill_file = (sk.path / "SKILL.md").resolve()
    skill_file.relative_to(sk.path.resolve())
    _, body = parse(_read_limited(skill_file))
    others = [str(p.relative_to(sk.path)) for p in islice(sk.path.rglob("*"), MAX_SCAN_FILES)
              if p.is_file() and p.name != "SKILL.md"][:40]
    extra = ("\n\n[Bu ko'nikma papkasidagi boshqa fayllar (use_skill(name, file=...) bilan o'qing): " + ", ".join(others) + "]") if others else ""
    return body + extra
