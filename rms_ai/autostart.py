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


def _looks_like_llm_root(path: Path) -> bool:
    """Return True if path looks like the local LLM gateways workspace."""
    return (
        (path / "freellm" / "server" / "dist" / "index.js").is_file()
        or (path / "litellm_config.yaml").is_file()
        or (path / ".venv" / "Scripts" / "litellm.exe").is_file()
    )


def find_llm_root(llm_root: str | Path | None = None) -> Path | None:
    """Locate the local LLM gateways directory from explicit arg, env, or standard paths."""
    candidates: list[Path] = []
    if llm_root:
        candidates.append(Path(llm_root))
    env_root = os.environ.get("RMS_AI_LLM_DIR", "").strip()
    if env_root:
        candidates.append(Path(env_root))
    if sys.platform == "win32":
        candidates.extend([Path("D:/llm"), Path("C:/llm")])
    candidates.extend([
        Path.home() / "llm",
        Path(__file__).resolve().parent.parent.parent / "llm",
    ])
    for candidate in candidates:
        try:
            if candidate.is_dir() and _looks_like_llm_root(candidate):
                return candidate
        except OSError:
            continue
    return None


def _find_node() -> str | None:
    """Locate the Node.js executable."""
    node_bin = shutil.which("node")
    if node_bin:
        return node_bin
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
            if not base:
                continue
            for sub in (Path("nodejs") / "node.exe", Path("Programs") / "nodejs" / "node.exe"):
                candidate = Path(base) / sub
                if candidate.is_file():
                    return str(candidate)
    return None


def ensure_local_services(llm_root: str | Path | None = None) -> list[str]:
    """Start local AI gateways (Ollama, FreeLLMAPI, g4f, LiteLLM) if installed and not running."""
    started: list[str] = []

    if not _is_port_open("127.0.0.1", 11434):
        ollama_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        ollama_bin = str(ollama_exe) if ollama_exe.is_file() else shutil.which("ollama")
        if ollama_bin and _spawn_background([ollama_bin, "serve"]):
            started.append("ollama")

    root = find_llm_root(llm_root)
    if root is None:
        return started

    freellm_dir = root / "freellm"
    freellm_entry = freellm_dir / "server" / "dist" / "index.js"
    if not _is_port_open("127.0.0.1", 3001) and freellm_entry.is_file():
        node_bin = _find_node()
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
