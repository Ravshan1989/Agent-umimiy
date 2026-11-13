"""Veb-server rejimi: lokal tarmoqdagi odamlar brauzer orqali kirib, o'z suhbatlarida agentlardan foydalanadi.

Oynasiz ishlaydi (`agent-umimiy --serve`). Har bir foydalanuvchining o'z logini va suhbatlari bor; javoblar
brauzerga oqim (Server-Sent Events) bilan boradi. Agentlar bu rejimda serverdagi fayllarga, buyruqlarga,
brauzerga va plaginlarga tegmaydi: faqat suhbat, biriktirilgan fayllar va (yoqilgan bo'lsa) veb-qidiruv.
Ulanish oddiy HTTP: ishonchli lokal tarmoqda ishlating yoki oldiga HTTPS beruvchi proksi qo'ying.
"""
from __future__ import annotations

import json
import mimetypes
import queue
import shutil
import socketserver
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import attachments, config, preview, remote
from .server_page import PAGE
from .store import SESSION_DAYS, Store, StoreError

MAX_BODY = 40 * 1024 * 1024
MAX_FILES = 6
MAX_PROMPT = 100_000
MAX_LIVE_TEXT = 200_000
SSE_QUEUE_SIZE = 256
MAX_CONNECTIONS = 64
MAX_DOWNLOAD = 50 * 1024 * 1024
TITLE_LEN = 40
LOCAL_ONLY = ("cli",)  # serverda buyruq ishga tushiradigan agent turlari: veb-foydalanuvchilarga berilmaydi
STATIC_DIR = Path(__file__).parent / "static"
PAGE_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
# Yaratiladigan fayl turlari (tizim sozlamasiga bog'liq bo'lmasligi uchun aniq ro'yxat)
FILE_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
}
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
    def orchestrator(self, user_id: int | None = None):
        cfg = config.read(self.config_file)
        cfg["agents"] = [a for a in cfg["agents"] if a.get("type") not in LOCAL_ONLY]
        orch = config.build(cfg)
        ctx = orch.ctx
        ctx.root = ctx.confirm = ctx.mcp = None
        ctx.browser = False
        ctx.web, ctx.skills = bool(cfg.get("web", True)), bool(cfg.get("skills", True))
        if user_id is not None:
            ctx.memory_file = str(config.user_dir() / "memories" / f"{int(user_id)}.json")
        return orch

    def files_dir(self, chat_id: int) -> Path:
        """Shu suhbatda agent yaratgan fayllar papkasi."""
        return config.user_dir() / "files" / str(chat_id)

    def agents(self) -> list[dict]:
        lang = config.read(self.config_file).get("lang", "uz")
        automatic = {"uz": "Avtomatik — o‘zi tanlaydi", "ru": "Автоматический выбор", "en": "Automatic selection"}
        return [{"name": "auto", "model": automatic.get(lang, automatic["uz"])}] + [
            {"name": a.name, "model": a.options.get("model", "")} for a in self.orchestrator().agents.values()
        ]

    # ---- hodisalar ----
    def _channel(self, chat_id: int) -> Channel:
        return self.channels.setdefault(chat_id, Channel())

    def _publish(self, chat_id: int, event: dict, record: dict | None = None) -> None:
        with self.lock:
            ch = self._channel(chat_id)
            if record is not None:
                self.store.add_record(chat_id, record)
            for q in ch.subs:
                self._enqueue(q, event)

    def _record(self, chat_id: int, record: dict) -> None:
        self._publish(chat_id, {"type": "record", "record": record}, record)

    def _emit(self, chat_id: int, agent: str, kind: str, text: str) -> None:
        if kind == "file":  # brauzerga faqat fayl nomi beriladi, serverdagi yo'l emas
            text = Path(text).name
        if kind not in ("delta", "turn"):
            return self._record(chat_id, {"k": "act", "agent": agent, "kind": kind, "text": text})
        with self.lock:
            ch = self._channel(chat_id)
            ch.live[agent] = "" if kind == "turn" else (ch.live.get(agent, "") + text)[-MAX_LIVE_TEXT:]
            for q in ch.subs:
                self._enqueue(q, {"type": kind, "agent": agent, "text": text})

    @staticmethod
    def _enqueue(q: queue.Queue, event: dict) -> None:
        try:
            q.put_nowait(event)
        except queue.Full:
            # Slow SSE clients are disconnected; reconnect receives a full database snapshot.
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
            q.put_nowait({"type": "overflow"})

    def subscribe(self, chat_id: int) -> queue.Queue:
        """Tinglovchi navbati; birinchi hodisa — suhbatning hozirgi to'liq holati."""
        q: queue.Queue = queue.Queue(maxsize=SSE_QUEUE_SIZE)
        with self.lock:
            ch = self._channel(chat_id)
            self._enqueue(q, {"type": "init", "records": self.store.records(chat_id), "live": dict(ch.live), "busy": ch.busy})
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
    def send(self, chat_id: int, user_id: int, text: str, agent: str, files: list[dict]) -> None:
        if not isinstance(agent, str):
            raise Refused("Agent tanlovi noto'g'ri.")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise Refused("Fayllar ro'yxati noto'g'ri.")
        orch = self.orchestrator(user_id)
        if agent != "auto" and agent not in orch.agents:
            raise Refused("Bu agent mavjud emas. Sahifani yangilang.")
        orch.ctx.files_dir = str(self.files_dir(chat_id))
        if len(files) > MAX_FILES:
            raise Refused(f"Bir xabarda ko'pi bilan {MAX_FILES} ta fayl yuborish mumkin.")
        if not isinstance(text, str):
            raise Refused("Xabar matni noto'g'ri.")
        text = text.strip()
        if len(text) > MAX_PROMPT:
            raise Refused(f"Xabar {MAX_PROMPT} belgidan oshmasin.")
        # Suhbatni oldindan band qilamiz: band chatga kelgan fayllar diskka yozilmaydi.
        with self.lock:
            ch = self._channel(chat_id)
            if ch.busy:
                raise Refused("Agent hozir band. To'xtatib, qayta urining.")
            try:
                self.store.title(chat_id)
            except IndexError:
                raise Refused("Suhbat topilmadi.", 404)
            ch.busy, ch.cancel, ch.live = True, None, {}
        atts = []
        try:
            for f in files:
                try:
                    atts.append(attachments.save_upload(config.upload_dir(), f.get("name", "fayl"), f.get("data", "")))
                except attachments.AttachError as exc:
                    raise Refused(str(exc))
            if not text and not atts:
                raise Refused("Xabar bo'sh.")
            prompt = text or "Biriktirilgan fayl(lar)ni ko'rib chiq va qisqacha tushuntir."
            if not self.store.title(chat_id):
                self.store.set_title(chat_id, prompt.replace("\n", " ")[:TITLE_LEN])
            self._record(chat_id, {"k": "user", "text": prompt, "files": [a.name for a in atts]})
            self._publish(chat_id, {"type": "busy", "agent": agent})
            with self.lock:
                ch = self._channel(chat_id)
                ch.cancel = orch.ctx.cancel
            threading.Thread(target=self._work, args=(chat_id, orch, prompt, agent, atts), daemon=True).start()
        except Exception:
            for att in atts:
                try:
                    Path(att.path).unlink(missing_ok=True)
                except OSError:
                    pass
            with self.lock:
                ch = self.channels.get(chat_id)
                if ch:
                    ch.busy, ch.cancel, ch.live = False, None, {}
            raise

    def _work(self, chat_id: int, orch, prompt: str, agent: str, atts: list) -> None:
        try:
            orch.history = self.store.history(chat_id)
            orch.ctx.emit = lambda name, kind, text: self._emit(chat_id, name, kind, text)
            if agent == "auto":
                results = orch.run(prompt, "auto", files=atts)
            else:
                results = orch.run(prompt, "single", [agent], atts)
            for r in results:
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
                    self._enqueue(q, {"type": "done"})
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
        shutil.rmtree(self.files_dir(chat_id), ignore_errors=True)


class Throttle:
    """Parol va taklif kodini terib ko'rishga qarshi: bir manzildan 10 daqiqada 20 ta xato urinish."""

    WINDOW, LIMIT = 600, 20

    def __init__(self):
        self.fails: dict[str, list[float]] = {}
        self.sends: dict[int, list[float]] = {}
        self.lock = threading.Lock()

    def _prune(self, now: float) -> None:
        for address, attempts in list(self.fails.items()):
            active = [stamp for stamp in attempts if now - stamp < self.WINDOW]
            if active:
                self.fails[address] = active
            else:
                self.fails.pop(address, None)
        if len(self.fails) >= 4096:
            for address in list(self.fails)[:256]:
                self.fails.pop(address, None)

    def fail(self, ip: str) -> None:
        with self.lock:
            now = time.time()
            self._prune(now)
            self.fails[ip] = [t for t in self.fails.get(ip, []) if now - t < self.WINDOW] + [now]

    def locked(self, ip: str) -> bool:
        with self.lock:
            now = time.time()
            self._prune(now)
            return len([t for t in self.fails.get(ip, []) if now - t < self.WINDOW]) >= self.LIMIT

    def allow_send(self, user_id: int) -> bool:
        """Bir foydalanuvchining LLM xarajatini cheklash: 60 soniyada 20 ta yuborish."""
        with self.lock:
            now = time.time()
            for uid, attempts in list(self.sends.items()):
                active = [stamp for stamp in attempts if now - stamp < 60]
                if active:
                    self.sends[uid] = active
                else:
                    self.sends.pop(uid, None)
            if len(self.sends) >= 4096 and user_id not in self.sends:
                for uid in list(self.sends)[:256]:
                    self.sends.pop(uid, None)
            attempts = self.sends.get(user_id, [])
            if len(attempts) >= 20:
                return False
            self.sends[user_id] = attempts + [now]
            return True



def safe_file_path(base, name: str) -> Path | None:
    """Foydalanuvchi faylini faqat suhbat papkasi ichidan, symlink'larsiz tanlaydi."""
    if not isinstance(name, str) or not name or name != Path(name).name:
        return None
    try:
        root = Path(base).resolve()
        candidate = root / name
        if candidate.is_symlink():
            return None
        path = candidate.resolve(strict=True)
        if root not in path.parents or not path.is_file():
            return None
        return path
    except (OSError, RuntimeError, ValueError):
        return None


def make_handler(app: App):
    store, throttle = app.store, Throttle()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(30)  # sekin yuboriladigan so'rovlar server oqimini band qilmasin
        server_version = "AgentUmimiy"

        def log_message(self, *a):
            pass

        # ---- javob ----
        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", cookie: str = "",
                  download: str = "", csp: str = PAGE_CSP):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", csp)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            if download:
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(download)}")
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
                    index = STATIC_WEB_DIR / "index.html"
                    if index.is_file():
                        return self._send(200, index.read_bytes(), "text/html; charset=utf-8")
                    return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                if url.path.startswith("/assets/"):
                    root = STATIC_WEB_DIR.resolve()
                    asset = (STATIC_WEB_DIR / url.path.lstrip("/")).resolve()
                    if root not in asset.parents or not asset.is_file():
                        raise Refused("Fayl topilmadi.", 404)
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    return self._send(200, asset.read_bytes(), content_type)
                if url.path == "/manifest.webmanifest":
                    return self._send(200, MANIFEST, "application/manifest+json")
                if url.path in ICONS:
                    return self._send(200, (STATIC_DIR / url.path[1:]).read_bytes(), "image/png")
                if url.path == "/api/me":
                    user_id, name = self._user()
                    return self._json(200, {"user": name, "agents": app.agents(), "chats": store.chats(user_id)})
                if url.path == "/api/memory":
                    user_id, _ = self._user()
                    from . import memory
                    path = config.user_dir() / "memories" / f"{user_id}.json"
                    return self._json(200, {"items": memory.list_items(path)})
                if url.path == "/api/stream":
                    user_id, _ = self._user()
                    return self._stream(self._chat(user_id, parse_qs(url.query).get("chat", [""])[0]))
                if url.path == "/api/file":
                    user_id, _ = self._user()
                    query = parse_qs(url.query)
                    return self._file(self._chat(user_id, query.get("chat", [""])[0]), query.get("name", [""])[0],
                                      bool(query.get("view")))
                raise Refused("Topilmadi.", 404)
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})
            except Exception:
                self._json(500, {"error": "Ichki server xatoligi."})

        def do_POST(self):
            try:
                self._json(200, *self._post(urlparse(self.path).path, self._body()))
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})
            except StoreError as exc:
                self._json(400, {"error": str(exc)})
            except Exception:
                self._json(500, {"error": "Ichki server xatoligi. Qayta urinib ko'ring."})

        def _body(self) -> dict:
            # JSON turi talab qilinadi: boshqa saytdagi forma bunday so'rov yubora olmaydi (CSRF himoyasi)
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise Refused("Noto'g'ri so'rov.", 415)
            raw_size = self.headers.get("Content-Length")
            if raw_size is None:
                raise Refused("Content-Length sarlavhasi yo'q.")
            if not str(raw_size).isascii() or not str(raw_size).isdecimal():
                raise Refused("Noto'g'ri so'rov.")
            size = int(raw_size)
            # Manfiy uzunlik rfile.read(-1) ni ulanish EOF bo'lguncha kutishga majbur
            # qilishi mumkin; juda katta uzunlik esa xotirani tugatishi mumkin.
            if size < 0:
                raise Refused("Noto'g'ri so'rov.")
            if size > MAX_BODY:
                self.close_connection = True
                raise Refused("Hajm juda katta.", 413)
            try:
                raw_body = self.rfile.read(size)
                if len(raw_body) != size:
                    self.close_connection = True
                    raise Refused("So'rov tanasi to'liq kelmadi.")
                body = json.loads(raw_body or b"{}")
            except (ValueError, UnicodeDecodeError):
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
            if path == "/api/memory/delete":
                from . import memory
                item_id = str(body.get("id", "")).strip()
                if not item_id:
                    raise Refused("Xotira ID ko'rsatilmagan.")
                memory.forget(item_id, config.user_dir() / "memories" / f"{user_id}.json")
                return {"ok": True}, ""
            if path == "/api/memory/remember":
                from . import memory
                fact = str(body.get("fact", "")).strip()
                if not fact:
                    raise Refused("Saqlanadigan ma'lumot bo'sh.")
                return {"message": memory.remember(fact, config.user_dir() / "memories" / f"{user_id}.json")}, ""
            if path == "/api/chat/new":
                if len(store.chats(user_id)) >= 100:
                    raise Refused("Bir foydalanuvchi ko'pi bilan 100 ta suhbat yaratishi mumkin.", 429)
                return {"id": store.new_chat(user_id)}, ""
            chat_id = self._chat(user_id, body.get("chat"))
            if path == "/api/chat/delete":
                app.delete_chat(chat_id)
            elif path == "/api/send":
                if not throttle.allow_send(user_id):
                    raise Refused("Yuborish limiti: 60 soniyada 20 ta xabar. Biroz kuting.", 429)
                files = body.get("files") or []
                if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
                    raise Refused("Noto'g'ri so'rov.")
                app.send(chat_id, user_id, str(body.get("text", "")), str(body.get("agent", "")), files)
            elif path == "/api/stop":
                app.stop(chat_id)
            else:
                raise Refused("Topilmadi.", 404)
            return {"ok": True}, ""

        def _file(self, chat_id: int, name: str, view: bool):
            """Agent shu suhbatda yaratgan fayl: yuklab beradi yoki (view) qum qutisidagi ko'rinish sahifasini beradi."""
            path = safe_file_path(app.files_dir(chat_id), name)
            if path is None:
                raise Refused("Fayl topilmadi.", 404)
            if path.stat().st_size > MAX_DOWNLOAD:
                raise Refused("Fayl 50 MB dan katta; uni kichikroq qismlarga ajrating.", 413)
            page = preview.page(path) if view else None
            if page is not None:
                return self._send(200, page.encode(), "text/html; charset=utf-8", csp=preview.CSP)
            ctype = FILE_TYPES.get(path.suffix.lower(), "application/octet-stream")  # .html faqat ko'rinishda ochiladi
            self._send(200, path.read_bytes(), ctype, download=name)

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
                        event = q.get(timeout=15)
                        chunk = "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                    except queue.Empty:
                        event, chunk = None, ": ping\n\n"  # ulanish tirikligini bildiradi va uzilganini aniqlaydi
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
                    if event and event.get("type") == "overflow":
                        break  # EventSource qayta ulanadi va to'liq tarixni init orqali oladi
            except OSError:
                pass  # brauzer yopildi
            finally:
                app.unsubscribe(chat_id, q)

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    store: Store

    def __init__(self, *args, **kwargs):
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

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
