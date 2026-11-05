"""MCP (Model Context Protocol) mijozi: tayyor "plaginlar"ni (GitHub, fayllar, Notion, ...) agentlarga asbob qilib beradi.

Transportlar: stdio (kompyuterda ishga tushadigan dastur, masalan `npx ...`) va HTTP (masofaviy server, Bearer kalit bilan).
OAuth talab qiladigan masofaviy serverlar hozircha qo'llanmaydi.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request

from .tools import Tool

PROTOCOL = "2024-11-05"
MAX_TOOLS = 100

# Tayyor shablonlar: (nomi, tavsif, sozlama). {papka} kabi joylar foydalanuvchi to'ldiradi.
PRESETS = [
    {"label": "Fayllar (Filesystem)", "note": "Tanlangan papkadagi fayllar bilan ishlash. Buyruq oxiriga papka yo'lini yozing.",
     "name": "fayllar", "transport": "stdio", "command": "npx -y @modelcontextprotocol/server-filesystem C:\\Users\\Siz\\Documents"},
    {"label": "Xotira (Memory)", "note": "Agent suhbatlar orasida narsalarni eslab qoladi.",
     "name": "xotira", "transport": "stdio", "command": "npx -y @modelcontextprotocol/server-memory"},
    {"label": "Chuqur fikrlash", "note": "Murakkab masalalarni bosqichma-bosqich o'ylash.",
     "name": "fikrlash", "transport": "stdio", "command": "npx -y @modelcontextprotocol/server-sequential-thinking"},
    {"label": "Hujjatlar (Context7)", "note": "Kutubxonalarning so'nggi rasmiy hujjatlari.",
     "name": "hujjatlar", "transport": "stdio", "command": "npx -y @upstash/context7-mcp"},
    {"label": "Notion", "note": "Notion integratsiya tokenini (secret_...) NOTION_TOKEN ga yozing.",
     "name": "notion", "transport": "stdio", "command": "npx -y @notionhq/notion-mcp-server", "env": "NOTION_TOKEN=secret_..."},
    {"label": "Playwright brauzeri", "note": "Qo'shimcha brauzer avtomatlashtirish (ko'p imkoniyatli).",
     "name": "playwright", "transport": "stdio", "command": "npx -y @playwright/mcp@latest"},
    {"label": "GitHub (masofaviy)", "note": "GitHub shaxsiy token (PAT) kerak: Authorization: Bearer ghp_...",
     "name": "github", "transport": "http", "url": "https://api.githubcopilot.com/mcp/", "headers": "Authorization: Bearer ghp_..."},
    {"label": "Boshqa (o'zim kiritaman)", "note": "Istalgan MCP server: buyruq yoki URL.",
     "name": "", "transport": "stdio", "command": ""},
]


class McpError(Exception):
    pass


def _kv_lines(text: str, sep: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        if sep in line and line.strip() and not line.strip().startswith("#"):
            k, v = line.split(sep, 1)
            out[k.strip()] = v.strip()
    return out


def _result_text(res: dict) -> str:
    parts = []
    for c in res.get("content", []) or []:
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
        elif c.get("type") == "image":
            parts.append("[rasm — ko'rsatilmaydi]")
        elif c.get("type") == "resource":
            r = c.get("resource", {})
            parts.append(r.get("text") or f"[resurs: {r.get('uri', '')}]")
        else:
            parts.append(f"[{c.get('type', '?')}]")
    if not parts and res.get("structuredContent") is not None:
        parts.append(json.dumps(res["structuredContent"], ensure_ascii=False))
    return "\n".join(parts) or "(bo'sh natija)"


# ------------------------------- stdio -------------------------------
class StdioTransport:
    def __init__(self, command: str, env: dict, cwd: str | None = None):
        self.command, self.env, self.cwd = command, env, cwd
        self.proc: subprocess.Popen | None = None
        self.pending: dict[int, dict] = {}
        self.lock = threading.Lock()
        self.next_id = 0
        self.err_tail = ""

    def start(self):
        win = sys.platform == "win32"
        argv = [x[1:-1] if len(x) > 1 and x[0] == x[-1] and x[0] in "\"'" else x
                for x in shlex.split(self.command, posix=not win)]
        if not argv:
            raise McpError("Buyruq bo'sh")
        exe = shutil.which(argv[0])
        if not exe:
            hint = " Node.js ni nodejs.org dan o'rnating." if argv[0] in ("npx", "node", "npm") else ""
            raise McpError(f"«{argv[0]}» dasturi topilmadi.{hint}")
        self.proc = subprocess.Popen(
            [exe] + argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, **self.env}, cwd=self.cwd, bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read_out(self):
        buf = b""
        while True:
            chunk = self.proc.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    self._dispatch(json.loads(line))
                except ValueError:
                    continue
        for slot in list(self.pending.values()):  # server yopildi
            slot["error"] = "Server to'xtadi. " + self.err_tail[-300:]
            slot["event"].set()

    def _read_err(self):
        while True:
            chunk = self.proc.stderr.read(4096)
            if not chunk:
                break
            self.err_tail = (self.err_tail + chunk.decode("utf-8", errors="replace"))[-2000:]

    def _send(self, obj: dict):
        data = (json.dumps(obj) + "\n").encode()
        try:
            self.proc.stdin.write(data)
            self.proc.stdin.flush()
        except (OSError, ValueError):
            raise McpError("Serverga yozib bo'lmadi (to'xtagan)")

    def _dispatch(self, msg: dict):
        if "id" in msg and ("result" in msg or "error" in msg):
            slot = self.pending.get(msg["id"])
            if slot:
                slot["msg"] = msg
                slot["event"].set()
        elif "id" in msg and "method" in msg:  # serverdan so'rov: ping — javob, qolganlari — qo'llanmaydi
            if msg["method"] == "ping":
                self._send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
            else:
                self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Qo'llanmaydi"}})

    def request(self, method: str, params: dict | None = None, timeout: float = 120) -> dict:
        with self.lock:
            self.next_id += 1
            mid = self.next_id
        slot = {"event": threading.Event(), "msg": None, "error": None}
        self.pending[mid] = slot
        try:
            self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
            if not slot["event"].wait(timeout):
                raise McpError(f"Server javob bermadi ({method}, {int(timeout)} s)")
        finally:
            self.pending.pop(mid, None)
        if slot["error"]:
            raise McpError(slot["error"])
        msg = slot["msg"]
        if "error" in msg:
            raise McpError(str(msg["error"].get("message", msg["error"])))
        return msg["result"]

    def notify(self, method: str, params: dict | None = None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for pipe in (getattr(self.proc, "stdout", None), getattr(self.proc, "stderr", None)):
            try:
                pipe and pipe.close()
            except OSError:
                pass


# ------------------------------- HTTP -------------------------------
class HttpTransport:
    def __init__(self, url: str, headers: dict):
        self.url, self.headers, self.session = url, headers, None
        self.next_id = 0
        self.lock = threading.Lock()

    def start(self):
        if not self.url.lower().startswith(("http://", "https://")):
            raise McpError("URL http:// yoki https:// bilan boshlanishi kerak")

    def _post(self, body: dict, timeout: float, want_id: int | None):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **self.headers}
        if self.session:
            h["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session = sid
                if want_id is None:
                    return None
                ctype = r.headers.get("Content-Type", "")
                if "text/event-stream" in ctype:
                    data = []
                    for raw in r:
                        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                        if line.startswith("data:"):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            try:
                                msg = json.loads("\n".join(data))
                            except ValueError:
                                msg = {}
                            data = []
                            if msg.get("id") == want_id:
                                return msg
                    raise McpError("Server javob yubormadi")
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200]
            if exc.code in (401, 403):
                raise McpError(f"Ruxsat yo'q (HTTP {exc.code}): kalitni tekshiring. Server OAuth talab qilsa, hozircha qo'llanmaydi.")
            raise McpError(f"HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise McpError(f"Ulanib bo'lmadi: {exc.reason}")

    def request(self, method: str, params: dict | None = None, timeout: float = 120) -> dict:
        with self.lock:
            self.next_id += 1
            mid = self.next_id
        msg = self._post({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}, timeout, mid)
        if "error" in msg:
            raise McpError(str(msg["error"].get("message", msg["error"])))
        return msg["result"]

    def notify(self, method: str, params: dict | None = None):
        self._post({"jsonrpc": "2.0", "method": method, "params": params or {}}, 30, None)

    def close(self):
        pass


# ------------------------------- boshqaruvchi -------------------------------
class Server:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name = cfg["name"]
        self.transport = None
        self.tools: list[dict] = []
        self.status = "kutilmoqda"  # kutilmoqda | ulanmoqda | tayyor | xato | o'chiq
        self.error = ""

    def connect(self):
        self.status, self.error = "ulanmoqda", ""
        try:
            c = self.cfg
            if c.get("transport") == "http":
                self.transport = HttpTransport(c.get("url", ""), _kv_lines(c.get("headers", ""), ":"))
            else:
                self.transport = StdioTransport(c.get("command", ""), _kv_lines(c.get("env", ""), "="), c.get("cwd") or None)
            self.transport.start()
            self.transport.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                                  "clientInfo": {"name": "agent-umimiy", "version": "0.1"}}, timeout=180)
            self.transport.notify("notifications/initialized")
            tools, cursor = [], None
            while True:
                res = self.transport.request("tools/list", {"cursor": cursor} if cursor else {}, timeout=60)
                tools += res.get("tools", [])
                cursor = res.get("nextCursor")
                if not cursor:
                    break
            self.tools = tools
            self.status = "tayyor"
        except Exception as exc:
            self.status, self.error = "xato", str(exc)
            tail = getattr(self.transport, "err_tail", "")
            if tail.strip():
                self.error += " | " + tail.strip().splitlines()[-1][:200]
            self.close()

    def close(self):
        if self.transport:
            self.transport.close()


class Manager:
    def __init__(self, cfgs: list[dict] | None = None):
        self.servers: dict[str, Server] = {}
        self.lock = threading.Lock()
        self.configure(cfgs or [])

    def configure(self, cfgs: list[dict]):
        """Sozlama o'zgarganda: o'zgarmaganlari tegilmaydi, yangilari ulanadi, o'chirilganlari to'xtatiladi."""
        with self.lock:
            wanted = {c["name"]: c for c in cfgs if c.get("name") and c.get("enabled", True)}
            for name in list(self.servers):
                if name not in wanted or self.servers[name].cfg != wanted[name]:
                    threading.Thread(target=self.servers.pop(name).close, daemon=True).start()
            for name, c in wanted.items():
                if name not in self.servers:
                    s = self.servers[name] = Server(c)
                    threading.Thread(target=s.connect, daemon=True).start()

    def reconnect(self, name: str):
        with self.lock:
            s = self.servers.get(name)
            if s:
                cfg = s.cfg
                threading.Thread(target=s.close, daemon=True).start()
                s = self.servers[name] = Server(cfg)
                threading.Thread(target=s.connect, daemon=True).start()

    def wait_ready(self, timeout: float = 30) -> None:
        import time
        end = time.time() + timeout
        while time.time() < end and any(s.status in ("kutilmoqda", "ulanmoqda") for s in list(self.servers.values())):
            time.sleep(0.1)

    def tools(self) -> list[Tool]:
        out, used = [], set()
        for s in list(self.servers.values()):
            if s.status != "tayyor":
                continue
            for t in s.tools:
                name = re.sub(r"[^A-Za-z0-9_-]", "_", f"{s.name}__{t.get('name', '')}")[:64]
                while name in used:
                    name = name[:61] + "_x"
                used.add(name)
                schema = t.get("inputSchema") or {"type": "object", "properties": {}}
                schema = {k: v for k, v in schema.items() if k != "$schema"}
                if schema.get("type") != "object":
                    schema = {"type": "object", "properties": {}}
                tool = Tool(name, f"[{s.name}] {t.get('description', '') or t.get('title', '')}"[:900], schema, "mcp")
                tool.server, tool.remote_name = s.name, t.get("name", "")
                tool.read_only = bool((t.get("annotations") or {}).get("readOnlyHint"))
                out.append(tool)
        return out[:MAX_TOOLS]

    def call(self, server: str, tool: str, args: dict) -> str:
        s = self.servers.get(server)
        if not s or s.status != "tayyor":
            raise McpError(f"«{server}» plagini ulanmagan")
        res = s.transport.request("tools/call", {"name": tool, "arguments": args or {}}, timeout=120)
        text = _result_text(res)
        if res.get("isError"):
            raise McpError(text)
        return text

    def shutdown(self):
        for s in list(self.servers.values()):
            s.close()
        self.servers.clear()
