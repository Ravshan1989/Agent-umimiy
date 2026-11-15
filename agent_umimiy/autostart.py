from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

_STARTED_LOCK = threading.Lock()
_STARTED_ONCE = False


def _is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    """Return True if a TCP service is already listening on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _spawn_background(cmd: list[str], cwd: str | None = None) -> bool:
    """Launch a detached, windowless background process."""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if cwd:
        kwargs["cwd"] = cwd
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    try:
        subprocess.Popen(cmd, **kwargs)
        return True
    except OSError:
        return False


def ensure_local_services(llm_root: str | Path | None = None) -> list[str]:
    """Start local AI gateways (Ollama, FreeLLMAPI, g4f, LiteLLM) if installed and not running."""
    raw_root = llm_root or os.environ.get("AGENT_UMIMIY_LLM_DIR", "").strip()
    if not raw_root:
        return []
    root = Path(raw_root)
    started: list[str] = []

    if not _is_port_open("127.0.0.1", 11434):
        ollama_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        ollama_bin = str(ollama_exe) if ollama_exe.is_file() else shutil.which("ollama")
        if ollama_bin and _spawn_background([ollama_bin, "serve"]):
            started.append("ollama")

    freellm_dir = root / "freellm"
    freellm_entry = freellm_dir / "server" / "dist" / "index.js"
    if not _is_port_open("127.0.0.1", 3001) and freellm_entry.is_file():
        node_bin = shutil.which("node")
        if node_bin and _spawn_background([node_bin, str(Path("server") / "dist" / "index.js")], cwd=str(freellm_dir)):
            started.append("freellmapi")

    venv_scripts = root / ".venv" / "Scripts"
    py_bin = venv_scripts / "pythonw.exe"
    if not py_bin.is_file():
        py_bin = venv_scripts / "python.exe"
    if not _is_port_open("127.0.0.1", 1337) and py_bin.is_file():
        if _spawn_background([str(py_bin), "-m", "g4f", "--bind", "127.0.0.1:1337"], cwd=str(root)):
            started.append("g4f")

    litellm_bin = venv_scripts / "litellm.exe"
    litellm_cfg = root / "litellm_config.yaml"
    if not _is_port_open("127.0.0.1", 4000) and litellm_bin.is_file() and litellm_cfg.is_file():
        if _spawn_background(
            [str(litellm_bin), "--config", str(litellm_cfg), "--host", "127.0.0.1", "--port", "4000"],
            cwd=str(root),
        ):
            started.append("litellm")

    return started


def start_local_services_async(llm_root: str | Path | None = None) -> None:
    """Trigger ensure_local_services once in a daemon thread so UI startup stays instant."""
    global _STARTED_ONCE
    with _STARTED_LOCK:
        if _STARTED_ONCE:
            return
        _STARTED_ONCE = True
    threading.Thread(target=ensure_local_services, args=(llm_root,), daemon=True).start()
