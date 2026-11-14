"""Avtomatlashtirish va Jadval (Cron/Interval) moduli: belgilangan vaqt oralig'ida yoki
bir tugma bilan agent vazifalarini fonda bajaradi va natijasini saqlaydi."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

from . import config

MAX_JOBS = 30
_LOCK = threading.Lock()


def _jobs_path() -> Path:
    return config.user_dir() / "automations.json"


def list_jobs() -> list[dict]:
    p = _jobs_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _save_jobs(jobs: list[dict]) -> None:
    p = _jobs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(jobs[:MAX_JOBS], indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def add_job(title: str, prompt: str, agent: str = "auto", interval_minutes: int = 60) -> dict:
    title = str(title or "").strip()[:100]
    prompt = str(prompt or "").strip()[:4000]
    if not title or not prompt:
        raise ValueError("Sarlavha va topshiriq matni kiritilishi shart.")
    interval = max(5, min(int(interval_minutes or 60), 10080))
    with _LOCK:
        jobs = list_jobs()
        if len(jobs) >= MAX_JOBS:
            raise ValueError(f"Ko'pi bilan {MAX_JOBS} ta avtomat vazifa yaratish mumkin.")
        job_id = max((int(j.get("id", 0)) for j in jobs), default=0) + 1
        job = {
            "id": job_id,
            "title": title,
            "prompt": prompt,
            "agent": str(agent or "auto")[:64],
            "interval_minutes": interval,
            "enabled": True,
            "last_run": 0,
            "last_status": "kutilmoqda",
            "last_result": "",
        }
        jobs.append(job)
        _save_jobs(jobs)
        return job


def delete_job(job_id: int) -> list[dict]:
    with _LOCK:
        jobs = [j for j in list_jobs() if int(j.get("id", 0)) != int(job_id)]
        _save_jobs(jobs)
        return jobs


def toggle_job(job_id: int) -> list[dict]:
    with _LOCK:
        jobs = list_jobs()
        for j in jobs:
            if int(j.get("id", 0)) == int(job_id):
                j["enabled"] = not bool(j.get("enabled", True))
        _save_jobs(jobs)
        return jobs


def run_job_now(job_id: int, runner_fn: Callable[[str, str], str]) -> list[dict]:
    with _LOCK:
        jobs = list_jobs()
        target = next((j for j in jobs if int(j.get("id", 0)) == int(job_id)), None)
        if not target:
            raise ValueError("Vazifa topilmadi.")
        target["last_status"] = "bajarilmoqda"
        _save_jobs(jobs)

    def _bg():
        try:
            out = runner_fn(str(target.get("prompt", "")), str(target.get("agent", "auto")))
            status = "bajarildi"
        except Exception as exc:
            out = f"Xato: {exc}"
            status = "xato"
        with _LOCK:
            current = list_jobs()
            for j in current:
                if int(j.get("id", 0)) == int(job_id):
                    j["last_run"] = int(time.time())
                    j["last_status"] = status
                    j["last_result"] = str(out or "")[:2000]
            _save_jobs(current)

    threading.Thread(target=_bg, daemon=True).start()
    return list_jobs()


class Scheduler:
    """Fon rejimida vaqti kelgan avtomat vazifalarni ishga tushiradi."""

    def __init__(self, runner_fn: Callable[[str, str], str]):
        self.runner_fn = runner_fn
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(30):
            now = int(time.time())
            for job in list_jobs():
                if self._stop.is_set():
                    return
                if not job.get("enabled", True) or job.get("last_status") == "bajarilmoqda":
                    continue
                interval_sec = max(300, int(job.get("interval_minutes", 60)) * 60)
                last_run = int(job.get("last_run") or 0)
                if last_run > 0 and now - last_run >= interval_sec:
                    try:
                        run_job_now(int(job["id"]), self.runner_fn)
                    except Exception:
                        pass
