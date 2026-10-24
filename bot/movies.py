import base64
import json
import re
from dataclasses import dataclass

import aiohttp

TRACE_URL = "https://api.trace.moe/search?anilistInfo"
ANIME_MIN_SIMILARITY = 0.90
CLAUDE_PROMPT = (
    "Bu rasm kino, serial yoki multfilmdan olingan kadr bo'lishi mumkin. "
    "Faqat kontekstga tayanib (sarlavha, subtitr, logotip, afisha, o'ziga xos sahna) qaysi asar ekanini aniqla. "
    "Odamni yuzidan tanima. Ishonching komil bo'lmasa, o'ylab topma. "
    'Faqat JSON qaytar: {"title": str|null, "year": int|null, "type": "kino"|"serial"|"multfilm"|null, '
    '"confidence": "yuqori"|"o\'rta"|"past", "reason": str}. Topolmasang title ni null qil.'
)


@dataclass(frozen=True)
class MovieMatch:
    title: str
    source: str  # "trace.moe" yoki "claude"
    year: int | None = None
    kind: str | None = None
    detail: str | None = None  # masalan: "12-qism, 03:45"
    confidence: str | None = None


def format_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def parse_trace(data: dict) -> MovieMatch | None:
    results = data.get("result") or []
    if not results:
        return None
    top = results[0]
    if top.get("similarity", 0) < ANIME_MIN_SIMILARITY:
        return None
    anilist = top.get("anilist")
    if isinstance(anilist, dict):
        t = anilist.get("title") or {}
        title = t.get("english") or t.get("romaji") or t.get("native")
    else:
        title = top.get("filename")
    if not title:
        return None
    ep = top.get("episode")
    parts = []
    if ep is not None:
        parts.append(f"{ep}-qism")
    if top.get("from") is not None:
        parts.append(format_time(top["from"]))
    return MovieMatch(title=title, source="trace.moe", kind="anime", detail=", ".join(parts) or None,
                      confidence="yuqori")


async def search_anime(image: bytes, session: aiohttp.ClientSession) -> MovieMatch | None:
    async with session.post(TRACE_URL, data=image, headers={"Content-Type": "image/jpeg"},
                            timeout=aiohttp.ClientTimeout(total=30)) as r:
        if r.status != 200:
            return None
        return parse_trace(await r.json())


def parse_claude_reply(text: str) -> MovieMatch | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    title = d.get("title")
    if not title or d.get("confidence") == "past":
        return None
    year = d.get("year")
    return MovieMatch(title=str(title), source="claude", year=year if isinstance(year, int) else None,
                      kind=d.get("type"), detail=d.get("reason"), confidence=d.get("confidence"))


async def search_with_claude(image: bytes, api_key: str, model: str) -> MovieMatch | None:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    msg = await client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                         "data": base64.b64encode(image).decode()}},
            {"type": "text", "text": CLAUDE_PROMPT},
        ]}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "text", None))
    return parse_claude_reply(text)


async def find_movie(image: bytes, api_key: str = "", model: str = "") -> MovieMatch | None:
    async with aiohttp.ClientSession() as session:
        try:
            match = await search_anime(image, session)
        except Exception:
            match = None
    if match:
        return match
    if api_key:
        return await search_with_claude(image, api_key, model)
    return None


def format_match(m: MovieMatch) -> str:
    head = f"🎬 <b>{m.title}</b>"
    if m.year:
        head += f" ({m.year})"
    lines = [head]
    if m.kind:
        lines.append(f"Turi: {m.kind}")
    if m.detail:
        lines.append(f"{'Epizod' if m.source == 'trace.moe' else 'Izoh'}: {m.detail}")
    if m.source == "claude":
        lines.append(f"Ishonch: {m.confidence or 'noma`lum'} (sun'iy intellekt taxmini, xato bo'lishi mumkin)")
    return "\n".join(lines)
