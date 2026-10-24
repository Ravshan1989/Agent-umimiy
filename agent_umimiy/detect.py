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


def _get(url: str, timeout: float = 1.5, key: str = ""):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key} if key else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def list_models(base_url: str, key: str = "", timeout: float = 8) -> list[str]:
    """OpenAI-mos shlyuzdan (FreeLLMAPI, LM Studio, OpenRouter...) model nomlari ro'yxatini oladi."""
    data = _get(base_url.rstrip("/") + "/models", timeout, key)
    return [m["id"] for m in data.get("data", []) if "id" in m]


def freellmapi(base: str = "http://localhost:3001") -> list[dict]:
    """FreeLLMAPI lokal shlyuzi ishlayotgan bo'lsa, agent sifatida taklif qiladi (kalitni foydalanuvchi kiritadi)."""
    import urllib.error
    url = base.rstrip("/") + "/v1"
    model = "auto"
    try:
        ids = list_models(url, timeout=1.5)
        model = ids[0] if ids else model
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403):  # kalit so'raydi — demak shlyuz bor
            return []
    except Exception:
        return []
    return [{"name": "freellmapi", "type": "openai", "base_url": url, "model": model,
             "description": "FreeLLMAPI (lokal shlyuz) — API kalitni Sozlamalarda kiriting"}]


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
    return local_servers() + freellmapi() + cli_agents()
