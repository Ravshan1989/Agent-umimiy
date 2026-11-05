"""Sinov uchun oddiy MCP server (stdio): initialize, tools/list, tools/call."""
import json
import sys

TOOLS = [
    {"name": "echo", "description": "Matnni qaytaradi", "annotations": {"readOnlyHint": True},
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "$schema": "x"}},
    {"name": "save-note", "description": "Eslatma saqlaydi", "inputSchema": {"type": "object", "properties": {"note": {"type": "string"}}}},
    {"name": "boom", "description": "Xato beradi", "annotations": {"readOnlyHint": True}, "inputSchema": {"type": "object", "properties": {}}},
]
saved = []
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    m, p, out = msg["method"], msg.get("params", {}), None
    if m == "initialize":
        out = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
    elif m == "tools/list":
        out = {"tools": TOOLS}
    elif m == "tools/call":
        n, a = p["name"], p.get("arguments", {})
        if n == "echo":
            out = {"content": [{"type": "text", "text": "echo: " + a["text"]}]}
        elif n == "save-note":
            saved.append(a.get("note"))
            out = {"content": [{"type": "text", "text": f"saqlandi ({len(saved)})"}]}
        else:
            out = {"content": [{"type": "text", "text": "buzildi"}], "isError": True}
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": out if out is not None else {}}), flush=True)
