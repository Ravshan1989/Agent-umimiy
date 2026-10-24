"""Telefondan boshqarish: kompyuterda kichik veb-server, kirish maxfiy kalit (token) bilan.

Server oyna (Tk) ga o'zi tegmaydi: hamma amal `handler(action, payload)` orqali, dasturning asosiy oqimida bajariladi.
Ulanish oddiy HTTP: faqat ishonchli uy tarmog'ida yoki Tailscale kabi shifrlangan tunnel orqali ishlating.
"""
from __future__ import annotations

import hmac
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .remote_page import PAGE

MAX_BODY = 40 * 1024 * 1024
ACTIONS = {"/api/send": "send", "/api/stop": "stop", "/api/approve": "approve", "/api/new": "new",
           "/api/close": "close", "/api/mode": "mode"}


def new_token() -> str:
    return secrets.token_urlsafe(24)


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # paket yuborilmaydi, faqat qaysi tarmoq ishlatilishini aniqlaydi
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class RemoteServer:
    def __init__(self, handler, token: str, port: int = 8765, host: str = "0.0.0.0"):
        self.handler, self.token, self.host = handler, token, host
        self.port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.fails: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    # ---- hayot sikli ----
    def start(self) -> int:
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            server_version = "AgentUmimiy"

            def log_message(self, *a):
                pass

            def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; "
                                 "connect-src 'self'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode())

            def _auth(self) -> bool:
                ip = self.client_address[0]
                if outer.locked(ip):
                    self._json(429, {"error": "Juda ko'p noto'g'ri urinish. 10 daqiqadan keyin qayta urining."})
                    return False
                if hmac.compare_digest(self.headers.get("X-Token", "").encode(), outer.token.encode()):
                    return True
                outer.fail(ip)
                time.sleep(0.5)
                self._json(401, {"error": "Ruxsat yo'q"})
                return False

            def do_GET(self):
                u = urlparse(self.path)
                if u.path == "/":
                    return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                if u.path == "/api/state":
                    if not self._auth():
                        return
                    q = parse_qs(u.query)
                    try:
                        chat = int(q["chat"][0]) if q.get("chat", [""])[0] != "" else None
                        since = int(q.get("since", ["0"])[0])
                    except ValueError:
                        return self._json(400, {"error": "noto'g'ri so'rov"})
                    return self._run("state", {"chat": chat, "since": since})
                self._json(404, {"error": "topilmadi"})

            def do_POST(self):
                action = ACTIONS.get(urlparse(self.path).path)
                if not action:
                    return self._json(404, {"error": "topilmadi"})
                if not self._auth():
                    return
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    if n > MAX_BODY:
                        return self._json(413, {"error": "Hajm juda katta"})
                    payload = json.loads(self.rfile.read(n) or b"{}")
                    if not isinstance(payload, dict):
                        raise ValueError
                except ValueError:
                    return self._json(400, {"error": "JSON noto'g'ri"})
                self._run(action, payload)

            def _run(self, action, payload):
                try:
                    self._json(200, outer.handler(action, payload))
                except Exception as exc:
                    self._json(400, {"error": str(exc)})

        for port in (self.port, 0):
            try:
                self.httpd = ThreadingHTTPServer((self.host, port), H)
                break
            except OSError:
                continue
        if not self.httpd:
            raise OSError("Port ochib bo'lmadi")
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self.port

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    # ---- brute-force himoyasi ----
    def fail(self, ip: str):
        with self.lock:
            now = time.time()
            self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < 600] + [now]

    def locked(self, ip: str) -> bool:
        with self.lock:
            now = time.time()
            return len([t for t in self.fails.get(ip, []) if now - t < 600]) >= 20

    def url(self, host: str | None = None) -> str:
        return f"http://{host or lan_ip()}:{self.port}/?t={self.token}"
