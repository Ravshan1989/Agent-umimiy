"""Kompyuterda mavjud agentlarni avtomatik topish (foydalanuvchi hech narsa yozmasligi uchun)."""
from __future__ import annotations

import json
import shutil
import urllib.request

CLI_TOOLS = {
    "claude": ("Claude Code", "claude -p {prompt}"),
    "codex": ("Codex", "codex exec {prompt}"),
    "gemini": ("Gemini CLI", "gemini -p {prompt}"),
    "aider": ("Aider", "aider --message {prompt}"),
}


def _get(url: str, timeout: float = 1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def local_servers() -> list[dict]:
    """Ollama va LM Studio ishlayotgan bo'lsa, ulardagi modellarni agent sifatida qaytaradi."""
    found = []
    try:
        for m in _get("http://localhost:11434/api/tags").get("models", []):
            found.append({"name": f"ollama-{m['name']}", "type": "ollama", "model": m["name"],
                          "description": "Lokal model (Ollama)"})
    except Exception:
        pass
    try:
        for m in _get("http://localhost:1234/v1/models").get("data", []):
            found.append({"name": f"lmstudio-{m['id']}", "type": "openai", "model": m["id"],
                          "base_url": "http://localhost:1234/v1", "api_key": "lm-studio",
                          "description": "Lokal model (LM Studio)"})
    except Exception:
        pass
    return found


def cli_agents() -> list[dict]:
    return [{"name": key, "type": "cli", "command": cmd, "description": title}
            for key, (title, cmd) in CLI_TOOLS.items() if shutil.which(key)]


def discover() -> list[dict]:
    return local_servers() + cli_agents()
