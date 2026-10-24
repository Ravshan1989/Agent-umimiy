from __future__ import annotations

import os
import shlex
import subprocess

from . import agentic, proc
from . import attachments as att
from .base import Agent, AgentError, http_json


def _key(opts: dict, default_env: str) -> str:
    env = opts.get("api_key_env", default_env)
    key = opts.get("api_key") or os.environ.get(env, "")
    if not key:
        raise AgentError(f"API kalit topilmadi: {env} muhit o'zgaruvchisini o'rnating")
    return key


class AnthropicAgent(Agent):
    kind = "anthropic"
    supports_tools = True

    def _ask_tools(self, prompt, history, tb):
        return agentic.anthropic(self.options, _key(self.options, "ANTHROPIC_API_KEY"), prompt, history, tb, self._files)

    def _ask(self, prompt, history):
        o = self.options
        data = http_json(
            o.get("base_url", "https://api.anthropic.com") + "/v1/messages",
            {
                "model": o.get("model", "claude-sonnet-5-5"),
                "max_tokens": o.get("max_tokens", 2048),
                "messages": history + [{"role": "user", "content": att.anthropic_content(prompt, self._files)}],
            },
            {"x-api-key": _key(o, "ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
        )
        return "".join(b.get("text", "") for b in data.get("content", []))


class OpenAIAgent(Agent):
    """OpenAI va unga mos API'lar (OpenRouter, LM Studio, Groq, ...)."""

    kind = "openai"
    supports_tools = True

    def _ask_tools(self, prompt, history, tb):
        return agentic.openai(self.options, _key(self.options, "OPENAI_API_KEY"), prompt, history, tb, self._files)

    def _ask(self, prompt, history):
        o = self.options
        data = http_json(
            o.get("base_url", "https://api.openai.com/v1") + "/chat/completions",
            {
                "model": o.get("model", "gpt-4o"),
                "messages": history + [{"role": "user", "content": att.openai_content(prompt, self._files)}],
            },
            {"Authorization": "Bearer " + _key(o, "OPENAI_API_KEY")},
        )
        return data["choices"][0]["message"]["content"]


class GeminiAgent(Agent):
    kind = "gemini"

    def _ask(self, prompt, history):
        o = self.options
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in history
        ] + [{"role": "user", "parts": att.gemini_parts(prompt, self._files)}]
        model = o.get("model", "gemini-2.0-flash")
        data = http_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"contents": contents},
            {"x-goog-api-key": _key(o, "GEMINI_API_KEY")},
        )
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])


class OllamaAgent(Agent):
    """Lokal modellar (kalitsiz, offline)."""

    kind = "ollama"
    supports_tools = True

    def _ask_tools(self, prompt, history, tb):
        return agentic.ollama(self.options, prompt, history, tb, self._files)

    def _ask(self, prompt, history):
        o = self.options
        data = http_json(
            o.get("base_url", "http://localhost:11434") + "/api/chat",
            {
                "model": o.get("model", "llama3"),
                "messages": history + [att.ollama_message(prompt, self._files)],
                "stream": False,
            },
            {},
        )
        return data["message"]["content"]


class CLIAgent(Agent):
    """Kompyuterdagi istalgan CLI agent (claude, codex, gemini, aider, ...).

    `command` — masalan: "claude -p {prompt}" yoki "codex exec {prompt}".
    Agar {prompt} bo'lmasa, so'rov stdin orqali beriladi.
    """

    kind = "cli"

    def _ask(self, prompt, history):
        o = self.options
        template = o.get("command")
        if not template:
            raise AgentError("'command' ko'rsatilmagan")
        parts = shlex.split(template)
        use_stdin = not any("{prompt}" in p for p in parts)
        argv = [p.replace("{prompt}", prompt) for p in parts]
        ctx = getattr(self, "ctx", None)
        if self._files:
            prompt += "\n\nBiriktirilgan fayllar (to'liq yo'li):\n" + "\n".join(a.path for a in self._files)
            if use_stdin is False:
                argv = [p.replace("{prompt}", prompt) for p in parts]
        try:
            p = proc.run(argv, input=prompt if use_stdin else None, timeout=o.get("timeout", 300),
                         cwd=(ctx.root if ctx and ctx.root else o.get("cwd")) or None)
        except FileNotFoundError as exc:
            raise AgentError(f"Buyruq topilmadi: {argv[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AgentError("Vaqt tugadi") from exc
        if p.returncode != 0:
            raise AgentError(p.stderr.strip() or f"chiqish kodi {p.returncode}")
        return p.stdout.strip()


class EchoAgent(Agent):
    """Sinov va demo uchun: so'rovni qaytaradi."""

    kind = "echo"

    def _ask(self, prompt, history):
        extra = f" (+{', '.join(a.name for a in self._files)})" if self._files else ""
        return f"[{self.name}] {self.options.get('prefix', '')}{prompt}{extra}"


KINDS = {c.kind: c for c in (AnthropicAgent, OpenAIAgent, GeminiAgent, OllamaAgent, CLIAgent, EchoAgent)}


def build_agent(spec: dict) -> Agent:
    spec = dict(spec)
    kind = spec.pop("type")
    if kind not in KINDS:
        raise ValueError(f"Noma'lum agent turi: {kind} (mavjud: {', '.join(KINDS)})")
    name = spec.pop("name")
    desc = spec.pop("description", "")
    return KINDS[kind](name, desc, **spec)
