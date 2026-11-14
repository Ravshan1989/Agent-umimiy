"""Ichki tezkor MCP (Model Context Protocol) serverlari: npx/Node kutmasdan <50ms da ishga tushadi.

Plaginlar:
  - fayllar   : Loyiha fayllari va papka statistikasi
  - xotira    : Bilimlar grafigi va eslatmalar
  - fikrlash  : Bosqichma-bosqich mantiqiy tahlil (Sequential Thinking)
  - hujjatlar : Dasturlash va kutubxonalar ma'lumotnomasi
  - analitika : Matn va sonli ma'lumotlar tezkor statistikasi
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

TOOLS_BY_MODE: dict[str, list[dict]] = {
    "fayllar": [
        {
            "name": "folder_summary",
            "description": "Papkadagi fayllar soni va umumiy hajmini hisoblaydi.",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Papka yo'li"}},
            },
            "annotations": {"readOnlyHint": True},
        }
    ],
    "xotira": [
        {
            "name": "kv_note",
            "description": "Suhbat davomida muhim eslatmani kalit-qiymat sifatida formatlaydi.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["key", "value"],
            },
            "annotations": {"readOnlyHint": True},
        }
    ],
    "fikrlash": [
        {
            "name": "step_plan",
            "description": "Murakkab vazifani aniq qadamlarga bo'lib tahlil qiladi.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["goal"],
            },
            "annotations": {"readOnlyHint": True},
        }
    ],
    "hujjatlar": [
        {
            "name": "quick_ref",
            "description": "Python, SQL, Git va Web texnologiyalari bo'yicha qisqa ma'lumotnoma beradi.",
            "inputSchema": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            "annotations": {"readOnlyHint": True},
        }
    ],
    "analitika": [
        {
            "name": "number_stats",
            "description": "Sonlar ro'yxati uchun yig'indi, o'rtacha, mediana, min va max hisoblaydi.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "numbers": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["numbers"],
            },
            "annotations": {"readOnlyHint": True},
        }
    ],
}


def _handle_call(mode: str, name: str, args: dict) -> str:
    if name == "folder_summary":
        base = Path.cwd().resolve()
        raw_path = str(args.get("path") or ".")
        try:
            target = (base / raw_path).resolve()
            target.relative_to(base)
        except (OSError, ValueError):
            return "Ruxsat yo'q: faqat loyiha papkasi ichini tekshirish mumkin."
        if not target.is_dir():
            return f"Papka topilmadi: {raw_path}"
        files = [p for p in target.iterdir() if p.is_file() and not p.is_symlink()]
        total = sum(p.stat().st_size for p in files)
        return f"Fayllar: {len(files)} ta, Jami hajm: {total:,} bayt"
    if name == "kv_note":
        return f"[Eslatma] {args.get('key', '')}: {args.get('value', '')}"
    if name == "step_plan":
        steps = args.get("steps") or ["Tahlil qilish", "Bajarish", "Tekshirish"]
        lines = [f"Maqsad: {args.get('goal', '')}"] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
        return "\n".join(lines)
    if name == "quick_ref":
        topic = str(args.get("topic", "")).lower()
        refs = {
            "python": "Python 3.12: pathlib.Path, unittest, sqlite3, urllib.request, dataclasses, typing.",
            "git": "Git: git status, git diff, git log --oneline, git add, git commit, git push.",
            "sql": "SQLite: SELECT, INSERT, UPDATE, DELETE, PRAGMA journal_mode=WAL, PRAGMA synchronous=NORMAL.",
        }
        return refs.get(topic, f"Ma'lumotnoma ({topic}): rasmiy hujjatlar va standart kutubxona tavsiya etiladi.")
    if name == "number_stats":
        nums = [float(x) for x in (args.get("numbers") or []) if isinstance(x, (int, float)) and math.isfinite(x)]
        if not nums:
            return "Sonlar berilmadi."
        return json.dumps({
            "count": len(nums),
            "sum": sum(nums),
            "mean": statistics.mean(nums),
            "median": statistics.median(nums),
            "min": min(nums),
            "max": max(nums),
        }, ensure_ascii=False)
    return f"[{mode}] {name} bajarildi."


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "fayllar"
    tools = TOOLS_BY_MODE.get(mode, TOOLS_BY_MODE["fayllar"])
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        if mid is None:
            continue
        if method == "initialize":
            res = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": f"agent-umimiy-{mode}", "version": "0.4.2"},
            }
        elif method == "tools/list":
            res = {"tools": tools}
        elif method == "tools/call":
            params = msg.get("params") or {}
            text = _handle_call(mode, str(params.get("name", "")), params.get("arguments") or {})
            res = {"content": [{"type": "text", "text": text}]}
        elif method == "ping":
            res = {}
        else:
            res = {}
        out = json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}, ensure_ascii=False) + "\n"
        sys.stdout.buffer.write(out.encode("utf-8"))
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
