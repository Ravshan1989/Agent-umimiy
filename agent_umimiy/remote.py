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


def classify_ip(ip: str) -> tuple[int, str]:
    """(ustuvorlik, izoh): telefon bilan bir tarmoqda bo'lishi ehtimoli yuqori manzillar oldinda."""
    a = [int(x) for x in ip.split(".")]
    if ip.startswith("169.254."):
        return 9, "avtomatik manzil, ishlamaydi"
    if a[0] == 192 and a[1] == 168:
        if a[2] in (56, 99):
            return 5, "virtual (VirtualBox/Docker)"
        return 0, "uy Wi-Fi/Ethernet tarmog'i"
    if a[0] == 10:
        return 1, "uy yoki ofis tarmog'i"
    if a[0] == 172 and 16 <= a[1] <= 31:
        return 3, "ofis yoki virtual (Docker/WSL)"
    if a[0] == 100 and 64 <= a[1] <= 127:
        return 4, "Tailscale yoki operator tarmog'i"
    return 6, "boshqa"


def local_ips() -> list[dict]:
    """Kompyuterning barcha IPv4 manzillari, eng ehtimoliy (uy Wi-Fi'i) birinchi."""
    found: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    for target in ("8.8.8.8", "192.168.1.1", "192.168.0.1", "10.0.0.1"):  # paket yuborilmaydi: faqat qaysi tarmoq tanlanishini aniqlaydi
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 1))
                found.add(s.getsockname()[0])
        except OSError:
            pass
    found = {ip for ip in found if not ip.startswith("127.") and ip != "0.0.0.0"}
    out = [{"ip": ip, "score": classify_ip(ip)[0], "note": classify_ip(ip)[1]} for ip in found]
    return sorted((o for o in out if o["score"] < 9), key=lambda o: (o["score"], o["ip"]))


def lan_ip() -> str:
    ips = local_ips()
    return ips[0]["ip"] if ips else "127.0.0.1"


FIREWALL_RULE = "Agent Umimiy"


def firewall_args(port: int, exe: str | None = None) -> str:
    """Windows xavfsizlik devori uchun kiruvchi ulanish qoidasi (netsh argumentlari)."""
    args = f'advfirewall firewall add rule name="{FIREWALL_RULE}" dir=in action=allow protocol=TCP localport={port} profile=any enable=yes'
    return args + (f' program="{exe}"' if exe else "")


def firewall_rule_exists() -> bool:
    import sys
    if sys.platform != "win32":
        return False
    from . import proc
    try:
        p = proc.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"], timeout=15)
        return FIREWALL_RULE in p.stdout
    except Exception:
        return False


def open_firewall(port: int) -> tuple[bool, str]:
    """Windows'da administrator ruxsatini (UAC) so'rab, dastur uchun kiruvchi ulanishga ruxsat qoidasini qo'shadi."""
    import sys
    if sys.platform != "win32":
        return False, "Bu tugma faqat Windows uchun."
    import ctypes
    exe = sys.executable if getattr(sys, "frozen", False) else None
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", firewall_args(port, exe), None, 0)
    if r <= 32:
        return False, "Administrator ruxsati berilmadi. Qoida qo'shilmadi."
    return True, "Administrator so'rovida «Ha» ni bosing, so'ng bir necha soniya kuting."


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
