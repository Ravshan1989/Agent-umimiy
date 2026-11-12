"""Oqimli (streaming) javoblar: matn kelishi bilan `on_text` ga beriladi, oxirida to'liq xabar qaytadi.

Har bir provayder o'z formatida oqim yuboradi; bu modul ularni o'qib, oqimsiz javob bilan bir xil
ko'rinishdagi natijaga yig'adi. `on_text` istisno ko'tarsa (masalan, to'xtatish), oqim uziladi.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Callable

from .base import AgentError

TIMEOUT = 120  # ulanish va har bir bo'lakni kutish chegarasi (soniya)
OnText = Callable[[str], None]


def _friendly_http_error(status: int, body: str) -> str:
    try:
        payload = json.loads(body or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    error = payload.get("error", payload) if isinstance(payload, dict) else {}
    message = error.get("message", "") if isinstance(error, dict) else str(error)
    message = str(message or body or "Noma'lum API xatosi").strip()
    low = message.lower()
    if "no endpoints found" in low and ("image input" in low or "image support" in low):
        return ("Tanlangan model rasmni qabul qilmaydigan endpointga yo'naltirildi. "
                "OpenRouter modelini nvidia/nemotron-3.5-super-vl:free ga almashtiring. Tafsilot: " + message[:240])
    if status == 401:
        return "API kalit noto'g'ri yoki bekor qilingan. Kalitni provayder sozlamasidan tekshiring. " + message[:240]
    if status == 402:
        return "Provayder hisobida bepul limit tugagan yoki to'lov talab qilinmoqda. " + message[:240]
    if status == 429:
        return "So'rov limiti vaqtincha oshib ketdi. Biroz kutib qayta urinib ko'ring. " + message[:240]
    if status == 404 and ("model" in low or "endpoint" in low):
        return "Tanlangan model yoki API manzili topilmadi. Model nomi va manzilni tekshiring. " + message[:240]
    return f"HTTP {status}: {message[:500]}"


def _lines(url: str, payload: dict, headers: dict, sse: bool = False) -> Iterator[str]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if sse and resp.headers.get_content_type() == "application/json":
                _fail(json.loads(resp.read() or b"{}"))  # xato JSON ko'rinishida kelgan bo'lishi mumkin
                raise AgentError("Server oqimli (streaming) javobni qo'llab-quvvatlamaydi.")
            for raw in resp:
                yield raw.decode("utf-8", errors="replace").rstrip("\r\n")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise AgentError(_friendly_http_error(exc.code, body)) from exc
    except urllib.error.URLError as exc:
        raise AgentError(f"Ulanish xatosi: {exc.reason}") from exc
    except OSError as exc:  # oqim o'rtasida uzilish yoki vaqt tugashi
        raise AgentError(f"Ulanish uzildi: {exc}") from exc


def _fail(ev) -> None:
    err = ev.get("error") if isinstance(ev, dict) else None
    if err:
        raise AgentError("API xatosi: " + str(err.get("message", err) if isinstance(err, dict) else err)[:500])


def _events(url: str, payload: dict, headers: dict) -> Iterator[dict]:
    """Server-Sent Events: `data: {...}` qatorlari."""
    for line in _lines(url, payload, headers, sse=True):
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        ev = json.loads(data)
        _fail(ev)
        yield ev


def anthropic(url: str, payload: dict, headers: dict, on_text: OnText) -> list[dict]:
    """Anthropic Messages API -> to'liq `content` bloklari (matn va tool_use)."""
    blocks: dict[int, dict] = {}
    args: dict[int, str] = {}
    for ev in _events(url, {**payload, "stream": True}, headers):
        kind, i = ev.get("type"), ev.get("index")
        if kind == "content_block_start":
            blocks[i] = dict(ev["content_block"])
        elif kind == "content_block_delta":
            delta = ev["delta"]
            if delta.get("type") == "text_delta":
                blocks[i]["text"] = blocks[i].get("text", "") + delta["text"]
                on_text(delta["text"])
            elif delta.get("type") == "input_json_delta":
                args[i] = args.get(i, "") + delta["partial_json"]
        elif kind == "content_block_stop" and blocks.get(i, {}).get("type") == "tool_use":
            blocks[i]["input"] = json.loads(args.get(i) or "{}")
    return [blocks[i] for i in sorted(blocks)]


def openai(url: str, payload: dict, headers: dict, on_text: OnText) -> dict:
    """OpenAI-mos chat/completions -> yig'ilgan assistant xabari (matn va tool_calls)."""
    text, calls = "", {}
    for ev in _events(url, {**payload, "stream": True}, headers):
        for choice in ev.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                text += delta["content"]
                on_text(delta["content"])
            for c in delta.get("tool_calls") or []:
                slot = calls.setdefault(c.get("index", 0),
                                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                fn = c.get("function") or {}
                slot["id"] = c.get("id") or slot["id"]
                slot["function"]["name"] = fn.get("name") or slot["function"]["name"]
                slot["function"]["arguments"] += fn.get("arguments") or ""
    msg = {"role": "assistant", "content": text or None}
    if calls:
        msg["tool_calls"] = [calls[i] for i in sorted(calls)]
    return msg


def gemini(url: str, payload: dict, headers: dict, on_text: OnText) -> str:
    """Gemini streamGenerateContent (alt=sse) -> to'liq matn."""
    text = ""
    for ev in _events(url, payload, headers):
        for cand in ev.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                if part.get("text"):
                    text += part["text"]
                    on_text(part["text"])
    return text


def ollama(url: str, payload: dict, on_text: OnText) -> dict:
    """Ollama /api/chat (har qatorda bitta JSON) -> yig'ilgan assistant xabari."""
    msg: dict = {"role": "assistant", "content": ""}
    for line in _lines(url, {**payload, "stream": True}, {}):
        if not line.strip():
            continue
        ev = json.loads(line)
        _fail(ev)
        part = ev.get("message") or {}
        if part.get("content"):
            msg["content"] += part["content"]
            on_text(part["content"])
        if part.get("tool_calls"):
            msg.setdefault("tool_calls", []).extend(part["tool_calls"])
    return msg
