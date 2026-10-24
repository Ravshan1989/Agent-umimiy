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


INSTALL_HINT = {
    "claude": "PowerShell'da: npm install -g @anthropic-ai/claude-code --force  (yoki rasmiy o'rnatuvchi: irm https://claude.ai/install.ps1 | iex), "
              "so'ng `claude --version` bilan tekshiring.",
}


def cli_health(exe: str) -> tuple[bool, str]:
    """Dasturni ishga tushirmasdan tekshiradi: npm o'rnatishi tugallanmagan bo'lsa, `claude.exe` o'rnida matnli
    o'rindosh fayl qoladi va Windows «16-bitli dastur» xatosini beradi (va oynada qotib qoladi)."""
    import os
    import re
    try:
        low = exe.lower()
        if low.endswith(".exe"):
            targets = [exe]
        elif low.endswith((".cmd", ".bat")):
            text = open(exe, encoding="utf-8", errors="replace").read(20000)
            base = os.path.dirname(os.path.abspath(exe))
            targets = []
            for m in re.finditer(r'"(?:%~?dp0%?)[\\/]*([^"%]+?\.exe)"', text, re.I):
                targets.append(os.path.normpath(os.path.join(base, m.group(1).replace("\\", os.sep))))
        else:
            return True, ""
        for t in targets:
            if not os.path.isfile(t):
                continue
            with open(t, "rb") as fh:
                head = fh.read(2)
            if head != b"MZ":
                name = os.path.basename(exe).rsplit(".", 1)[0]
                hint = INSTALL_HINT.get(name.lower(), "Dasturni qayta o'rnating.")
                return False, (f"«{name}» o'rnatilishi buzilgan: {t} haqiqiy dastur emas (o'rnatish tugallanmagan). {hint}")
    except OSError:
        pass
    return True, ""


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
    out = []
    for key, (title, cmd) in CLI_TOOLS.items():
        exe = shutil.which(key)
        if exe and cli_health(exe)[0]:  # buzilgan o'rnatish agent sifatida taklif qilinmaydi
            out.append({"name": key, "type": "cli", "command": cmd, "description": title})
    return out


def discover() -> list[dict]:
    return local_servers() + freellmapi() + cli_agents()
