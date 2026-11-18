"""GitHub Releases orqali RMS AI dasturini avtomatik tekshirish va yangilash."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

DEFAULT_RELEASES_URL = "https://api.github.com/repos/Ravshan1989/RMS-AI/releases/latest"
INSTALLER_NAME = "RMSAI-Setup.exe"


def parse_version(raw: str) -> tuple[int, ...]:
    """'v0.7.3' yoki '0.7.2' ko'rinishidagi versiyani solishtirish uchun tuple ga o'giradi."""
    nums = [int(x) for x in re.findall(r"\d+", str(raw or ""))]
    return tuple(nums) if nums else (0,)


def _find_installer_url(assets: list) -> str:
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        url = str(item.get("browser_download_url", ""))
        if name.lower() == INSTALLER_NAME.lower() and url.startswith("https://"):
            return url
    for item in assets:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        url = str(item.get("browser_download_url", ""))
        if name.lower().endswith("-setup.exe") and url.startswith("https://"):
            return url
    return ""


def check_update(url: str | None = None, timeout: float = 5.0) -> dict:
    """Oxirgi relizni tekshiradi va yangilanish bor-yo'qligini qaytaradi."""
    target = (url or os.environ.get("RMS_UPDATE_URL", "") or DEFAULT_RELEASES_URL).strip()
    base = {
        "current_version": __version__,
        "latest_version": __version__,
        "update_available": False,
        "download_url": "",
        "release_notes": "",
        "html_url": "",
        "error": "",
    }
    if not target.startswith("https://"):
        base["error"] = "Yangilanish manzili HTTPS bo'lishi kerak."
        return base
    req = urllib.request.Request(
        target,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"RMSAI/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        with exc:  # javob tanasini yopadi (aks holda ResourceWarning)
            if exc.code == 404:
                base["error"] = "Hali GitHub Releases da nashr (release) joylanmagan."
            else:
                base["error"] = f"Server xatosi: HTTP {exc.code}"
            return base
    except Exception as exc:
        base["error"] = f"Internetga ulanib bo'lmadi: {exc}"
        return base

    tag = str(data.get("tag_name") or data.get("version") or "").strip()
    latest = tag.lstrip("vV") or __version__
    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    dl_url = str(data.get("download_url") or "") or _find_installer_url(assets)
    if not dl_url.startswith("https://"):
        dl_url = ""

    available = parse_version(latest) > parse_version(__version__) and bool(dl_url)
    base.update(
        {
            "latest_version": latest,
            "update_available": available,
            "download_url": dl_url,
            "release_notes": str(data.get("body") or "")[:1500],
            "html_url": str(data.get("html_url") or ""),
        }
    )
    return base


def _schedule_exit(delay: float = 0.8) -> None:
    threading.Timer(delay, lambda: os._exit(0)).start()


def install_update(download_url: str, timeout: float = 120.0) -> dict:
    """O'rnatuvchini yuklab oladi, fon rejimida ishga tushiradi va joriy oynani yopadi."""
    url = str(download_url or "").strip()
    if not url.startswith("https://"):
        raise ValueError("Yuklash manzili HTTPS bo'lishi kerak.")
    if sys.platform != "win32":
        raise RuntimeError("Avtomatik o'rnatish hozircha faqat Windows uchun qo'llab-quvvatlanadi.")

    dest = Path(tempfile.gettempdir()) / "RMSAI-Setup-update.exe"
    req = urllib.request.Request(url, headers={"User-Agent": f"RMSAI/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)

    cmd = [
        "cmd.exe",
        "/c",
        f'timeout /t 2 /nobreak >nul & start "" "{dest}" /SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS',
    ]
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
        close_fds=True,
    )
    _schedule_exit(0.8)
    return {"ok": True, "installer": str(dest)}
