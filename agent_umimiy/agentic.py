"""Asbob chaqiruvi sikli (agent o'zi fayl o'qiydi, tahrirlaydi, buyruq ishga tushiradi).

Anthropic, OpenAI-mos va Ollama uchun. Har bir sikl: model javob beradi -> asbob so'raydi -> biz bajaramiz ->
natijani qaytaramiz -> model yakuniy matn bergunga qadar.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from . import attachments as att
from . import stream
from .base import AgentError
from .tools import Cancelled, Toolbox, system_prompt

MAX_STEPS = 30


def _check(tb: Toolbox):
    if tb.ctx.cancel.is_set():
        raise Cancelled()


def _sink(tb: Toolbox):
    """Oqimli matn bo'laklarini hodisa sifatida uzatadi; to'xtatilgan bo'lsa oqimni uzadi."""
    def on_text(text: str):
        _check(tb)
        tb._say("delta", text)
    return on_text


def _next_turn(tb: Toolbox):
    """Asboblar bajarildi, model yangi javob boshlaydi: ko'rsatilayotgan oqimli matn tozalanadi."""
    tb._say("turn", "")


def _text_tool_calls(content: str, tools) -> list[dict]:
    """Recover XML-style function calls emitted as text by OpenAI-compatible models."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:xml)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    if not re.fullmatch(r"<function_calls>.*</function_calls>", text, flags=re.DOTALL | re.IGNORECASE):
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    available = {tool.name: tool for tool in tools}
    calls = []
    for index, invoke in enumerate(root.findall("invoke")):
        name = invoke.get("name", "")
        tool = available.get(name)
        if tool is None:
            continue
        schema = (tool.parameters.get("properties") or {})
        args = {}
        for parameter in invoke.findall("parameter"):
            key = parameter.get("name", "")
            if not key or key not in schema:
                continue
            value = "".join(parameter.itertext()).strip()
            kind = schema[key].get("type")
            if kind != "string":
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    continue
            args[key] = value
        calls.append({"id": f"text_call_{index}", "type": "function",
                      "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}})
    return calls


def anthropic(o: dict, key: str, prompt: str, history: list, tb: Toolbox, files=()) -> str:
    tools = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tb.tools()]
    messages = history + [{"role": "user", "content": att.anthropic_content(prompt, list(files))}]
    for _ in range(MAX_STEPS):
        _check(tb)
        content = stream.anthropic(
            o.get("base_url", "https://api.anthropic.com") + "/v1/messages",
            {"model": o.get("model", "claude-sonnet-5-5"), "max_tokens": o.get("max_tokens", 4096),
             "system": system_prompt(tb.ctx, tb.agent), "tools": tools, "messages": messages},
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            _sink(tb),
        )
        messages.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            return "".join(b.get("text", "") for b in content)
        results = []
        for u in uses:
            out, is_err = tb.run(u["name"], u.get("input") or {})
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": out, "is_error": is_err})
        messages.append({"role": "user", "content": results})
        _next_turn(tb)
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")


def openai(o: dict, key: str, prompt: str, history: list, tb: Toolbox, files=()) -> str:
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                               "parameters": t.parameters}} for t in tb.tools()]
    messages = [{"role": "system", "content": system_prompt(tb.ctx, tb.agent)}] + history + [
        {"role": "user", "content": att.openai_content(prompt, list(files))}]
    for _ in range(MAX_STEPS):
        _check(tb)
        msg = stream.openai(
            o.get("base_url", "https://api.openai.com/v1") + "/chat/completions",
            stream.openai_payload(
                {"model": att.openai_model_for(o, list(files)), "messages": messages, "tools": tools}, o),
            {"Authorization": "Bearer " + key},
            _sink(tb),
        )
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            calls = _text_tool_calls(msg.get("content") or "", tb.tools())
            if not calls:
                return msg.get("content") or ""
            messages[-1] = {"role": "assistant", "content": None, "tool_calls": calls}
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            out, _err = tb.run(c["function"]["name"], args)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": out})
        _next_turn(tb)
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")


def ollama(o: dict, prompt: str, history: list, tb: Toolbox, files=()) -> str:
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description,
                                               "parameters": t.parameters}} for t in tb.tools()]
    messages = [{"role": "system", "content": system_prompt(tb.ctx, tb.agent)}] + history + [att.ollama_message(prompt, list(files))]
    for _ in range(MAX_STEPS):
        _check(tb)
        msg = stream.ollama(o.get("base_url", "http://localhost:11434") + "/api/chat",
                            {"model": o.get("model", "llama3"), "messages": messages, "tools": tools}, _sink(tb))
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
        _next_turn(tb)
    raise AgentError(f"Agent {MAX_STEPS} qadamda tugata olmadi.")
