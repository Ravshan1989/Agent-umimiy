"""Veb-server rejimi: lokal tarmoqdagi odamlar brauzer orqali kirib, o'z suhbatlarida agentlardan foydalanadi.

Oynasiz ishlaydi (`agent-umimiy --serve`). Har bir foydalanuvchining o'z logini va suhbatlari bor; javoblar
brauzerga oqim (Server-Sent Events) bilan boradi. Agentlar bu rejimda serverdagi fayllarga, buyruqlarga,
brauzerga va plaginlarga tegmaydi: faqat suhbat, biriktirilgan fayllar va (yoqilgan bo'lsa) veb-qidiruv.
Ulanish oddiy HTTP: ishonchli lokal tarmoqda ishlating yoki oldiga HTTPS beruvchi proksi qo'ying.
"""
from __future__ import annotations

import json
import queue
import socketserver
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import attachments, config, remote
from .server_page import PAGE
from .store import SESSION_DAYS, Store, StoreError

MAX_BODY = 40 * 1024 * 1024
MAX_FILES = 6
TITLE_LEN = 40
LOCAL_ONLY = ("cli",)  # serverda buyruq ishga tushiradigan agent turlari: veb-foydalanuvchilarga berilmaydi
STATIC_DIR = Path(__file__).parent / "static"
ICONS = {"/icon-192.png": 192, "/icon-512.png": 512, "/apple-touch-icon.png": 180}
# Telefonda «Bosh ekranga qo'shish» orqali ilova kabi ochilishi uchun (PWA)
MANIFEST = json.dumps({
    "name": "Agent Umimiy", "short_name": "Agent Umimiy", "lang": "uz", "start_url": "/", "scope": "/",
    "display": "standalone", "background_color": "#0d0f16", "theme_color": "#0d0f16",
    "icons": [{"src": path, "sizes": f"{size}x{size}", "type": "image/png", "purpose": "any maskable"}
              for path, size in ICONS.items() if size != 180],
}).encode()


class Refused(Exception):
    """Foydalanuvchiga ko'rsatiladigan rad javobi."""

    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


class Channel:
    """Bitta suhbatning jonli holati: tinglovchilar, yozilayotgan matn va bandlik."""

    def __init__(self):
        self.subs: set[queue.Queue] = set()
        self.live: dict[str, str] = {}
        self.busy = False
        self.cancel: threading.Event | None = None


class App:
    """Server mantig'i (HTTP'dan mustaqil): suhbatlarni yuritadi va hodisalarni tinglovchilarga tarqatadi."""

    def __init__(self, store: Store, config_file: str | None = None):
        self.store, self.config_file = store, config_file
        self.lock = threading.Lock()
        self.channels: dict[int, Channel] = {}

    # ---- agentlar ----
    def orchestrator(self):
        cfg = config.read(self.config_file)
        cfg["agents"] = [a for a in cfg["agents"] if a.get("type") not in LOCAL_ONLY]
        orch = config.build(cfg)
        ctx = orch.ctx
        ctx.root = ctx.confirm = ctx.mcp = None
        ctx.browser = False
        ctx.web, ctx.skills = bool(cfg.get("web", True)), bool(cfg.get("skills", True))
        return orch

    def agents(self) -> list[dict]:
        return [{"name": a.name, "model": a.options.get("model", "")} for a in self.orchestrator().agents.values()]

    # ---- hodisalar ----
    def _channel(self, chat_id: int) -> Channel:
        return self.channels.setdefault(chat_id, Channel())

    def _publish(self, chat_id: int, event: dict, record: dict | None = None) -> None:
        with self.lock:
            ch = self._channel(chat_id)
            if record is not None:
                self.store.add_record(chat_id, record)
            for q in ch.subs:
                q.put(event)

    def _record(self, chat_id: int, record: dict) -> None:
        self._publish(chat_id, {"type": "record", "record": record}, record)

    def _emit(self, chat_id: int, agent: str, kind: str, text: str) -> None:
        if kind not in ("delta", "turn"):
            return self._record(chat_id, {"k": "act", "agent": agent, "kind": kind, "text": text})
        with self.lock:
            ch = self._channel(chat_id)
            ch.live[agent] = "" if kind == "turn" else ch.live.get(agent, "") + text
            for q in ch.subs:
                q.put({"type": kind, "agent": agent, "text": text})

    def subscribe(self, chat_id: int) -> queue.Queue:
        """Tinglovchi navbati; birinchi hodisa — suhbatning hozirgi to'liq holati."""
        q: queue.Queue = queue.Queue()
        with self.lock:
            ch = self._channel(chat_id)
            q.put({"type": "init", "records": self.store.records(chat_id), "live": dict(ch.live), "busy": ch.busy})
            ch.subs.add(q)
        return q

    def unsubscribe(self, chat_id: int, q: queue.Queue) -> None:
        with self.lock:
            ch = self.channels.get(chat_id)
            if ch:
                ch.subs.discard(q)
                if not ch.subs and not ch.busy:
                    del self.channels[chat_id]

    # ---- amallar ----
    def send(self, chat_id: int, text: str, agent: str, files: list[dict]) -> None:
        orch = self.orchestrator()
        if agent not in orch.agents:
            raise Refused("Bu agent mavjud emas. Sahifani yangilang.")
        try:
            atts = [attachments.save_upload(config.upload_dir(), f.get("name", "fayl"), f.get("data", ""))
                    for f in files[:MAX_FILES]]
        except attachments.AttachError as exc:
            raise Refused(str(exc))
        text = text.strip()
        if not text and not atts:
            raise Refused("Xabar bo'sh.")
        prompt = text or "Biriktirilgan fayl(lar)ni ko'rib chiq va qisqacha tushuntir."
        with self.lock:
            ch = self._channel(chat_id)
            if ch.busy:
                raise Refused("Agent hozir band. To'xtatib, qayta urining.")
            ch.busy, ch.cancel, ch.live = True, orch.ctx.cancel, {}
        if not self.store.title(chat_id):
            self.store.set_title(chat_id, prompt.replace("\n", " ")[:TITLE_LEN])
        self._record(chat_id, {"k": "user", "text": prompt, "files": [a.name for a in atts]})
        self._publish(chat_id, {"type": "busy", "agent": agent})
        threading.Thread(target=self._work, args=(chat_id, orch, prompt, agent, atts), daemon=True).start()

    def _work(self, chat_id: int, orch, prompt: str, agent: str, atts: list) -> None:
        try:
            orch.history = self.store.history(chat_id)
            orch.ctx.emit = lambda name, kind, text: self._emit(chat_id, name, kind, text)
            for r in orch.run(prompt, "single", [agent], atts):
                if r.ok:
                    record = {"k": "agent", "name": r.agent, "text": r.text or "(bo'sh javob)", "meta": f"{r.seconds:.1f} s"}
                else:
                    record = {"k": "agent", "name": r.agent, "text": r.error, "meta": "xato", "err": True}
                self._record(chat_id, record)
            self.store.set_history(chat_id, orch.history)
        except Exception as exc:  # bitta suhbatdagi xato serverni to'xtatmasligi kerak
            self._record(chat_id, {"k": "agent", "name": "Xato", "text": str(exc), "meta": "", "err": True})
        finally:
            with self.lock:
                ch = self._channel(chat_id)
                ch.busy, ch.cancel, ch.live = False, None, {}
                for q in ch.subs:
                    q.put({"type": "done"})
                if not ch.subs:
                    del self.channels[chat_id]

    def stop(self, chat_id: int) -> None:
        with self.lock:
            ch = self.channels.get(chat_id)
            if ch and ch.cancel:
                ch.cancel.set()

    def delete_chat(self, chat_id: int) -> None:
        with self.lock:
            ch = self.channels.get(chat_id)
            if ch and ch.busy:
                raise Refused("Agent hali ishlayapti. Avval to'xtating.")
            self.store.delete_chat(chat_id)


class Throttle:
    """Parol va taklif kodini terib ko'rishga qarshi: bir manzildan 10 daqiqada 20 ta xato urinish."""

    WINDOW, LIMIT = 600, 20

    def __init__(self):
        self.fails: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def fail(self, ip: str) -> None:
        with self.lock:
            now = time.time()
            self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < self.WINDOW] + [now]

    def locked(self, ip: str) -> bool:
        with self.lock:
            now = time.time()
            return len([t for t in self.fails.get(ip, []) if now - t < self.WINDOW]) >= self.LIMIT


def make_handler(app: App):
    store, throttle = app.store, Throttle()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "AgentUmimiy"

        def log_message(self, *a):
            pass

        # ---- javob ----
        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", cookie: str = ""):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                             "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj, cookie: str = ""):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), cookie=cookie)

        # ---- proksi ortida ----
        def _forwarded(self, header: str) -> str:
            """Proksi qo'shgan sarlavha; faqat so'rov shu kompyuterdagi proksidan kelganda ishoniladi."""
            if self.client_address[0] in ("127.0.0.1", "::1"):
                return self.headers.get(header, "").split(",")[0].strip()
            return ""

        def _ip(self) -> str:
            return self._forwarded("X-Forwarded-For") or self.client_address[0]

        def _cookie(self, value: str, age: int) -> str:
            secure = "; Secure" if self._forwarded("X-Forwarded-Proto") == "https" else ""
            return f"session={value}; Path=/; Max-Age={age}; HttpOnly; SameSite=Strict{secure}"

        # ---- kirish ----
        def _token(self) -> str:
            morsel = SimpleCookie(self.headers.get("Cookie", "")).get("session")
            return morsel.value if morsel else ""

        def _user(self) -> tuple[int, str]:
            user = store.session_user(self._token())
            if not user:
                raise Refused("Avval tizimga kiring.", 401)
            return user

        def _chat(self, user_id: int, raw) -> int:
            try:
                chat_id = int(raw)
            except (TypeError, ValueError):
                raise Refused("Suhbat topilmadi.", 404)
            if not store.owns(user_id, chat_id):
                raise Refused("Suhbat topilmadi.", 404)
            return chat_id

        # ---- yo'llar ----
        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path == "/":
                    return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                if url.path == "/manifest.webmanifest":
                    return self._send(200, MANIFEST, "application/manifest+json")
                if url.path in ICONS:
                    return self._send(200, (STATIC_DIR / url.path[1:]).read_bytes(), "image/png")
                if url.path == "/api/me":
                    user_id, name = self._user()
                    return self._json(200, {"user": name, "agents": app.agents(), "chats": store.chats(user_id)})
                if url.path == "/api/stream":
                    user_id, _ = self._user()
                    return self._stream(self._chat(user_id, parse_qs(url.query).get("chat", [""])[0]))
                raise Refused("Topilmadi.", 404)
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})

        def do_POST(self):
            try:
                self._json(200, *self._post(urlparse(self.path).path, self._body()))
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})
            except StoreError as exc:
                self._json(400, {"error": str(exc)})

        def _body(self) -> dict:
            # JSON turi talab qilinadi: boshqa saytdagi forma bunday so'rov yubora olmaydi (CSRF himoyasi)
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise Refused("Noto'g'ri so'rov.", 415)
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise Refused("Noto'g'ri so'rov.")
            if size > MAX_BODY:
                self.close_connection = True
                raise Refused("Hajm juda katta.", 413)
            try:
                body = json.loads(self.rfile.read(size) or b"{}")
            except ValueError:
                raise Refused("JSON noto'g'ri.")
            if not isinstance(body, dict):
                raise Refused("JSON noto'g'ri.")
            return body

        def _post(self, path: str, body: dict) -> tuple[dict, str]:
            """So'rovni bajaradi: (javob, o'rnatiladigan cookie)."""
            ip = self._ip()
            if path in ("/api/login", "/api/register"):
                if throttle.locked(ip):
                    raise Refused("Juda ko'p noto'g'ri urinish. 10 daqiqadan keyin qayta urining.", 429)
                name, password = str(body.get("name", "")), str(body.get("password", ""))
                if path == "/api/register":
                    if str(body.get("invite", "")).strip().upper() != store.invite():
                        throttle.fail(ip)
                        raise Refused("Taklif kodi noto'g'ri. Kodni server egasidan so'rang.", 403)
                    user_id = store.add_user(name, password)
                else:
                    user_id = store.check_user(name, password)
                    if user_id is None:
                        throttle.fail(ip)
                        raise Refused("Ism yoki parol noto'g'ri.", 403)
                return {"user": name.strip()}, self._cookie(store.new_session(user_id), SESSION_DAYS * 86400)
            if path == "/api/logout":
                store.drop_session(self._token())
                return {"ok": True}, self._cookie("", 0)
            user_id, _ = self._user()
            if path == "/api/chat/new":
                return {"id": store.new_chat(user_id)}, ""
            chat_id = self._chat(user_id, body.get("chat"))
            if path == "/api/chat/delete":
                app.delete_chat(chat_id)
            elif path == "/api/send":
                files = body.get("files") or []
                if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
                    raise Refused("Noto'g'ri so'rov.")
                app.send(chat_id, str(body.get("text", "")), str(body.get("agent", "")), files)
            elif path == "/api/stop":
                app.stop(chat_id)
            else:
                raise Refused("Topilmadi.", 404)
            return {"ok": True}, ""

        def _stream(self, chat_id: int):
            """Suhbat hodisalari oqimi (SSE). Ulanish uzilguncha ochiq turadi."""
            q = app.subscribe(chat_id)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Accel-Buffering", "no")  # nginx proksi oqimni ushlab qolmasin
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                while True:
                    try:
                        chunk = "data: " + json.dumps(q.get(timeout=15), ensure_ascii=False) + "\n\n"
                    except queue.Empty:
                        chunk = ": ping\n\n"  # ulanish tirikligini bildiradi va uzilganini aniqlaydi
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
            except OSError:
                pass  # brauzer yopildi
            finally:
                app.unsubscribe(chat_id, q)

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    store: Store

    def server_bind(self):  # standart usul socket.getfqdn() ni chaqiradi: Windows'da soniyalab qotib qolishi mumkin
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def create(store: Store, host: str = "127.0.0.1", port: int = 0, config_file: str | None = None) -> Server:
    httpd = Server((host, port), make_handler(App(store, config_file)))
    httpd.store = store
    return httpd


def open_default(host: str, port: int, config_file: str | None = None) -> Server:
    """Foydalanuvchi papkasidagi `server.db` bilan serverni ochadi (hali so'rov qabul qilmaydi)."""
    config.user_dir().mkdir(parents=True, exist_ok=True)
    store = Store(config.user_dir() / "server.db")
    try:
        return create(store, host, port, config_file)
    except OSError:
        store.close()
        raise


def start(host: str, port: int, config_file: str | None = None) -> Server:
    """Serverni fon oqimida ishga tushiradi (dastur oynasi ichidan)."""
    httpd = open_default(host, port, config_file)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def stop(httpd: Server) -> None:
    httpd.shutdown()
    httpd.server_close()
    httpd.store.close()


def urls(httpd: Server) -> list[str]:
    """Server ochiq bo'lgan manzillar (lokal tarmoqdagilar oldinda)."""
    host, port = httpd.server_address[0], httpd.server_port
    hosts = [o["ip"] for o in remote.local_ips()] if host == "0.0.0.0" else [host]
    return [f"http://{h}:{port}/" for h in hosts or ["127.0.0.1"]]


def run(host: str, port: int, config_file: str | None = None) -> None:
    httpd = open_default(host, port, config_file)
    print("Agent Umimiy veb-server ishga tushdi. Brauzerda oching:")
    for url in urls(httpd):
        print("  " + url)
    print(f"Ro'yxatdan o'tish uchun taklif kodi: {httpd.store.invite()}")
    print("To'xtatish: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        httpd.store.close()
