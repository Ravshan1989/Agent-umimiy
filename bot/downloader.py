import asyncio
import re
import tempfile
from pathlib import Path

import yt_dlp

URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class TooBigError(Exception):
    pass


def extract_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    return m.group(0) if m else None


def _download_sync(url: str, out_dir: Path, max_bytes: int) -> Path:
    opts = {
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        # Telegram 50 MB chegarasiga sig'adigan, mp4 ga yaqin format
        "format": f"best[ext=mp4][filesize<{max_bytes}]/best[filesize<{max_bytes}]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": max_bytes,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = [p for p in out_dir.iterdir() if p.is_file()]
    if not files:
        raise TooBigError()
    path = max(files, key=lambda p: p.stat().st_size)
    if path.stat().st_size > max_bytes:
        raise TooBigError()
    return path


async def download_video(url: str, out_dir: Path, max_mb: int = 50) -> Path:
    """Videoni out_dir ga yuklaydi va fayl yo'lini qaytaradi."""
    return await asyncio.to_thread(_download_sync, url, out_dir, max_mb * 1024 * 1024)


def make_temp_dir() -> tempfile.TemporaryDirectory:
    # Windows da fayl hali band bo'lishi mumkin; tozalash xatosi foydalanuvchiga ta'sir qilmasin
    return tempfile.TemporaryDirectory(prefix="dl_", ignore_cleanup_errors=True)
