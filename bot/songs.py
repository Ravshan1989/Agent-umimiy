import asyncio
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

MAX_RESULTS = 5
MAX_QUERY_LEN = 200


@dataclass(frozen=True)
class SongResult:
    video_id: str
    title: str
    duration: int | None


def _search_sync(query: str) -> list[SongResult]:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{MAX_RESULTS}:{query[:MAX_QUERY_LEN]}", download=False)
    results = []
    for e in (info or {}).get("entries") or []:
        if e and e.get("id") and e.get("title"):
            results.append(SongResult(e["id"], e["title"], e.get("duration")))
    return results


async def search_songs(query: str) -> list[SongResult]:
    """Nom yoki matn parchasi bo'yicha qo'shiq variantlarini qidiradi (kalit kerak emas)."""
    return await asyncio.to_thread(_search_sync, query)


def _download_sync(video_id: str, out_dir: Path, max_bytes: int) -> Path:
    opts = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "format": f"bestaudio[ext=m4a][filesize<{max_bytes}]/bestaudio[filesize<{max_bytes}]",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": max_bytes,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    files = [p for p in out_dir.iterdir() if p.is_file()]
    if not files:
        raise FileNotFoundError(video_id)
    return max(files, key=lambda p: p.stat().st_size)


async def download_audio(video_id: str, out_dir: Path, max_mb: int = 50) -> Path:
    return await asyncio.to_thread(_download_sync, video_id, out_dir, max_mb * 1024 * 1024)


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def button_label(song: SongResult, limit: int = 55) -> str:
    title = song.title if len(song.title) <= limit else song.title[: limit - 1] + "…"
    d = format_duration(song.duration)
    return f"{title} ({d})" if d else title
