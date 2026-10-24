"""Asbob chaqiruvi sikli (agent o'zi fayl o'qiydi, tahrirlaydi, buyruq ishga tushiradi).

Anthropic, OpenAI-mos va Ollama uchun. Har bir sikl: model javob beradi -> asbob so'raydi -> biz bajaramiz ->
natijani qaytaramiz -> model yakuniy matn bergunga qadar.
"""
from __future__ import annotations

import json

from .base import AgentError, http_json
from .tools import TOOLS, Cancelled, Toolbox, system_prompt

MAX_STEPS = 30


def _check(tb: Toolbox):
    if tb.ctx.cancel.is_set():
        raise Cancelled()


def anthropic(o: dict, key: str, prompt: str, history: list, tb: Toolbox) -> str:
    tools = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in TOOLS]
    messages = history + [{"role": "user", "content": prompt}]
    for _ in range(MAX_STEPS):
        _check(tb)
        data = http_json(
            o.get("base_url", "https://api.anthropic.com") + "/v1/messages",
            {"model": o.get("model", "claude-sonnet-5-5"), "max_tokens": o.get("max_tokens", 4096),
             "system": system_prompt(tb.ctx), "tools": tools, "messages": messages},
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        content = data.get("content", [])
        messages.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            return "".join(b.get("text", "") for b in content)
        results = []
        for u in uses:
            out, is_err = tb.run(u["name"], u.get("input") or {})
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out, "is_error": is_err})
        messages.append({"role": "user", "content": results})
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")


def openai(o: dict, key: str, prompt: str, history: list, tb: Toolbox) -> str:
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                               "parameters": t.parameters}} for t in TOOLS]
    messages = [{"role": "system", "content": system_prompt(tb.ctx)}] + history + [{"role": "user", "content": prompt}]
    for _ in range(MAX_STEPS):
        _check(tb)
        data = http_json(
            o.get("base_url", "https://api.openai.com/v1") + "/chat/completions",
            {"model": o.get("model", "gpt-4o"), "messages": messages, "tools": tools},
            {"Authorization": "Bearer " + key},
        )
        msg = data["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content") or ""
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out, _err = tb.run(c["function"]["name"], args)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")


def ollama(o: dict, prompt: str, history: list, tb: Toolbox) -> str:
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                               "parameters": t.parameters}} for t in TOOLS]
    messages = [{"role": "system", "content": system_prompt(tb.ctx)}] + history + [{"role": "user", "content": prompt}]
    for _ in range(MAX_STEPS):
        _check(tb)
        data = http_json(o.get("base_url", "http://localhost:11434") + "/api/chat",
                         {"model": o.get("model", "llama3"), "messages": messages, "tools": tools, "stream": False}, {})
        msg = data["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content", "")
        for c in calls:
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            out, _err = tb.run(c["function"]["name"], args)
            messages.append({"role": "tool", "tool_name": c["function"]["name"], "content": out})
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")
