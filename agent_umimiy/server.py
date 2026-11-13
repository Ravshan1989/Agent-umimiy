"""Veb-server rejimi: xodimlar tarmoq orqali o'z suhbatlarida agentlardan foydalanadi.

Har bir foydalanuvchining alohida ilova boshqaradigan brauzeri bor. Admin kompyuterining fayllari,
buyruqlari va plaginlari tarmoq foydalanuvchilariga ochilmaydi.
Ulanish oddiy HTTP: ishonchli lokal tarmoqda ishlating yoki oldiga HTTPS beruvchi proksi qo'ying.
"""
from __future__ import annotations

import getpass
import hmac
import json
import mimetypes
import queue
import re
import secrets
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import attachments, config, preview, remote, skills
from . import mcp as mcplib
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
DESKTOP_PORT = 47815  # desktop oynasi uchun doimiy port: brauzer xotirasi (vazifalar ro'yxati) saqlanib qoladi
LOCAL_ONLY = ("cli",)  # serverda buyruq ishga tushiradigan agent turlari: veb-foydalanuvchilarga berilmaydi
STATIC_DIR = Path(__file__).parent / "static"
PAGE_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
# Yaratiladigan fayl turlari (tizim sozlamasiga bog'liq bo'lmasligi uchun aniq ro'yxat)
FILE_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
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
        self.local_subs: set[queue.Queue] = set()
        self.live: dict[str, str] = {}
        self.approval: dict | None = None
        self.busy = False
        self.cancel: threading.Event | None = None


class App:
    """Server mantig'i (HTTP'dan mustaqil): suhbatlarni yuritadi va hodisalarni tinglovchilarga tarqatadi."""

    def __init__(self, store: Store, config_file: str | None = None):
        self.store, self.config_file = store, config_file
        self.lock = threading.Lock()
        self.channels: dict[int, Channel] = {}
        self.pending_approvals: dict[str, dict] = {}
        self.mcp_manager = None
        self.network_server = None
        self.network_error = ""
        self.desktop = False  # dastur o'z oynasida ishlayaptimi (run_desktop)
        self.desktop_token = ""  # oynani avtomatik kiritadigan bir martalik kalit
        self.classic_at = 0.0  # klassik oyna oxirgi marta qachon ochilgani

    # ---- agentlar ----
    def orchestrator(self, local_desktop: bool = False, chat_id: int | None = None,
                     user_id: int | None = None):
        cfg = config.read(self.config_file)
        if not local_desktop:  # web foydalanuvchilariga mahalliy agentlar berilmaydi
            cfg["agents"] = [a for a in cfg["agents"] if a.get("type") not in LOCAL_ONLY]
        orch = config.build(cfg)
        ctx = orch.ctx
        if local_desktop:
            project = cfg.get("project")
            ctx.root = project if isinstance(project, str) and Path(project).is_dir() else None
            if chat_id is not None and user_id is not None:
                ctx.confirm = lambda agent, kind, title, detail: self.request_approval(
                    chat_id, user_id, agent, kind, title, detail)
            ctx.browser = bool(cfg.get("browser", True))
            if self.mcp_manager:
                self.mcp_manager.configure(cfg.get("mcp", []))
            ctx.mcp = self.mcp_manager
            ctx.skills = bool(cfg.get("skills", True))
        else:
            ctx.root = None
            # Employees get a separate app-managed browser and administrator-enabled plugins,
            # but no direct host files, shell, or skills.
            ctx.confirm = None
            ctx.browser = bool(cfg.get("browser", True))
            ctx.browser_profile = (str(config.user_dir() / "browser-profiles" / f"user-{int(user_id)}-chat-{int(chat_id)}")
                                   if user_id is not None and chat_id is not None else None)
            ctx.remote_user = True
            ctx.skills = False
            if self.mcp_manager:
                self.mcp_manager.configure(cfg.get("mcp", []))
            ctx.mcp = self.mcp_manager
        ctx.web = bool(cfg.get("web", True))
        return orch

    def files_dir(self, chat_id: int) -> Path:
        """Shu suhbatda agent yaratgan fayllar papkasi."""
        return config.user_dir() / "files" / str(chat_id)

    def uploads_dir(self, chat_id: int) -> Path:
        """Shu suhbatga foydalanuvchi biriktirgan fayllar papkasi."""
        return self.files_dir(chat_id) / "uploads"

    def network_info(self) -> dict:
        server = self.network_server
        if not server:
            return {"enabled": False, "urls": [], "port": 0, "invite": "", "error": self.network_error}
        port = server.server_port
        return {"enabled": True, "urls": [f"http://{entry['ip']}:{port}/" for entry in remote.local_ips()],
                "port": port, "invite": self.store.invite(), "error": ""}

    def set_network(self, enabled: bool) -> dict:
        cfg = config.read(self.config_file)
        if enabled:
            if self.network_server:
                return self.network_info()
            try:
                port = int(cfg.get("server_port", 8080))
            except (TypeError, ValueError):
                raise Refused("Web-server porti son bo'lishi kerak.")
            if not 1 <= port <= 65535 or port == DESKTOP_PORT:
                raise Refused("Web-server porti noto'g'ri yoki desktop portiga teng.")
            server = Server(("0.0.0.0", port), make_handler(self))
            server.app, server.store = self, self.store
            self.network_server = server
            self.network_error = ""
            cfg["server"] = True
            config.write(cfg, self.config_file)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        else:
            server, self.network_server = self.network_server, None
            self.network_error = ""
            cfg["server"] = False
            config.write(cfg, self.config_file)
            if server:
                server.shutdown()
                server.server_close()
        return self.network_info()

    def agents(self, local_desktop: bool = False) -> list[dict]:
        return [{"name": "auto", "model": "Avtomatik — o‘zi tanlaydi"}] + [
            {"name": a.name, "model": a.options.get("model", "")}
            for a in self.orchestrator(local_desktop).agents.values()
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

    def subscribe(self, chat_id: int, local_desktop: bool = False) -> queue.Queue:
        """Tinglovchi navbati; birinchi hodisa — suhbatning hozirgi to'liq holati."""
        q: queue.Queue = queue.Queue(maxsize=SSE_QUEUE_SIZE)
        with self.lock:
            ch = self._channel(chat_id)
            initial = {"type": "init", "records": self.store.records(chat_id), "live": dict(ch.live), "busy": ch.busy}
            if local_desktop and ch.approval:
                initial["approval"] = dict(ch.approval)
            self._enqueue(q, initial)
            ch.subs.add(q)
            if local_desktop:
                ch.local_subs.add(q)
        return q

    def unsubscribe(self, chat_id: int, q: queue.Queue) -> None:
        with self.lock:
            ch = self.channels.get(chat_id)
            if ch:
                ch.subs.discard(q)
                ch.local_subs.discard(q)
                if not ch.subs and not ch.busy:
                    del self.channels[chat_id]

    def request_approval(self, chat_id: int, user_id: int, agent: str, kind: str,
                         title: str, detail: str) -> str:
        """Ask the chat owner before a browser action or local desktop operation."""
        approval_id = secrets.token_urlsafe(18)
        result = {"id": approval_id, "chat_id": chat_id, "user_id": user_id,
                  "answer": "no", "event": threading.Event()}
        public = {"id": approval_id, "agent": agent, "kind": kind,
                  "title": title[:300], "detail": detail[:8000]}
        with self.lock:
            self.pending_approvals[approval_id] = result
            ch = self._channel(chat_id)
            ch.approval = public
            for q in ch.local_subs:
                self._enqueue(q, {"type": "approval", "approval": public})
        result["event"].wait(timeout=300)
        with self.lock:
            self.pending_approvals.pop(approval_id, None)
            ch = self.channels.get(chat_id)
            if ch and ch.approval and ch.approval.get("id") == approval_id:
                ch.approval = None
                for q in ch.local_subs:
                    self._enqueue(q, {"type": "approval_done", "id": approval_id})
        return result["answer"]

    def resolve_approval(self, user_id: int, approval_id: str, answer: str) -> None:
        if answer not in ("yes", "always", "no"):
            raise Refused("Tasdiq javobi noto'g'ri.")
        with self.lock:
            pending = self.pending_approvals.get(approval_id)
            if not pending or pending["user_id"] != user_id or not self.store.owns(user_id, pending["chat_id"]):
                raise Refused("Ruxsat so'rovi topilmadi yoki muddati tugadi.", 404)
            pending["answer"] = answer
            pending["event"].set()

    def _cancel_approvals(self) -> None:
        with self.lock:
            for pending in self.pending_approvals.values():
                pending["answer"] = "no"
                pending["event"].set()

    # ---- amallar ----
    def send(self, chat_id: int, text: str, agent: str, files: list[dict],
             local_desktop: bool = False, user_id: int | None = None) -> None:
        if not isinstance(agent, str):
            raise Refused("Agent tanlovi noto'g'ri.")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise Refused("Fayllar ro'yxati noto'g'ri.")
        orch = self.orchestrator(local_desktop, chat_id, user_id)
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
                    # Suhbat papkasiga saqlanadi: shundagina foydalanuvchi uni qaytib yuklab ola oladi
                    # va suhbat o'chirilganda biriktirmalar ham o'chadi.
                    atts.append(attachments.save_upload(self.uploads_dir(chat_id), f.get("name", "fayl"), f.get("data", "")))
                except attachments.AttachError as exc:
                    raise Refused(str(exc))
            if not text and not atts:
                raise Refused("Xabar bo'sh.")
            prompt = text or "Biriktirilgan fayl(lar)ni ko'rib chiq va qisqacha tushuntir."
            if not self.store.title(chat_id):
                self.store.set_title(chat_id, prompt.replace("\n", " ")[:TITLE_LEN])
            # Ikkala nom ham kerak: "name" ko'rsatiladi, "file" esa diskdagi (vaqt belgili) nom — havola shu bilan ishlaydi.
            self._record(chat_id, {"k": "user", "text": prompt,
                                   "files": [{"name": a.name, "file": Path(a.path).name} for a in atts]})
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
            if not orch.history:
                # Older installs can have visible transcript records without the newer model-history field.
                # Rebuild user/assistant turns so returning to an existing chat keeps its context.
                rebuilt = []
                pending_user = None
                pending_answer = None
                def save_turn():
                    if pending_user is not None and pending_answer is not None:
                        rebuilt.extend(({"role": "user", "content": pending_user},
                                        {"role": "assistant", "content": pending_answer}))
                for item in self.store.records(chat_id):
                    if item.get("k") == "user":
                        save_turn()
                        pending_user = str(item.get("text", ""))
                        names = attached_names(item.get("files"))
                        if names:
                            pending_user += "\n\nBiriktirilgan fayllar: " + ", ".join(names)
                        pending_answer = None
                    elif item.get("k") == "agent" and pending_user is not None and not item.get("err"):
                        pending_answer = str(item.get("text", ""))
                save_turn()
                orch.history = rebuilt[-40:]
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

    def shutdown(self, timeout: float = 6.0) -> None:
        """Dastur yopilayotganda: ishlayotgan agentlarni to'xtatadi va javoblar bazaga yozilishini kutadi."""
        self._cancel_approvals()
        with self.lock:
            for channel in self.channels.values():
                if channel.cancel:
                    channel.cancel.set()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                if not any(channel.busy for channel in self.channels.values()):
                    break
            time.sleep(0.05)
        if self.mcp_manager:
            self.mcp_manager.shutdown()
            self.mcp_manager = None
        network_server, self.network_server = self.network_server, None
        if network_server:
            network_server.shutdown()
            network_server.server_close()
        from . import browser
        browser.shutdown()

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



def shown_name(name: str) -> str:
    """Biriktirma diskda `<millisekund>_asl-nom` bo'lib yotadi; foydalanuvchiga asl nomi ko'rinsin."""
    return re.sub(r"^\d{13}_(?=.)", "", str(name or ""))


def attached_names(files) -> list[str]:
    """Biriktirmalarning ko'rinadigan nomlari.

    Yangi yozuvlar {"name": ..., "file": ...} ko'rinishida, eskilari esa oddiy matn:
    ikkalasi ham ishlashi kerak, aks holda modelga dict'ning xom matni tushadi.
    """
    out = []
    for item in files or []:
        if isinstance(item, dict):
            out.append(str(item.get("name") or item.get("file") or "fayl"))
        elif isinstance(item, str):
            out.append(item)
    return out


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

        def handle_one_request(self):
            self.body_read = False  # har bir so'rov uchun qaytadan: ulanish keyingi so'rovga ham ishlatiladi
            super().handle_one_request()

        def _drain(self):
            """Javobdan oldin o'qilmagan so'rov tanasini bo'shatadi.

            Aks holda mijoz hali yubormoqchi bo'lgan ma'lumot o'qilmay qoladi va Windows ulanishni RST bilan uzadi:
            mijoz xato matnini (masalan 415 yoki 401 javobini) o'qiy olmaydi.
            """
            if getattr(self, "body_read", False) or self.command not in ("POST", "PUT", "PATCH"):
                return
            self.body_read = True
            raw = self.headers.get("Content-Length", "")
            if not str(raw).isascii() or not str(raw).isdecimal() or int(raw) > MAX_BODY:
                self.close_connection = True  # hajmi noma'lum yoki juda katta: o'qimaymiz, ulanishni yopamiz
                return
            left = int(raw)
            while left > 0:
                chunk = self.rfile.read(min(left, 65536))
                if not chunk:
                    self.close_connection = True
                    return
                left -= len(chunk)

        def log_message(self, *a):
            pass

        # ---- javob ----
        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8", cookie: str = "",
                  download: str = "", csp: str = PAGE_CSP):
            self._drain()
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

        def _desktop(self) -> bool:
            """So'rov dasturning o'z oynasidan kelganmi: desktop rejimi, shu kompyuter, proksisiz."""
            return (app.desktop and self.client_address[0] in ("127.0.0.1", "::1")
                    and not self.headers.get("X-Forwarded-For"))

        def _host_ok(self) -> bool:
            """DNS rebinding himoyasi: desktop rejimida brauzer sayti lokal serverni o'z domeni orqali ocholmaydi."""
            if not app.desktop or self.client_address[0] not in ("127.0.0.1", "::1"):
                return True  # --serve rejimi va lokal tarmoq mijozlari: Host ularning manzili bo'ladi
            host = self.headers.get("Host", "")
            if host.startswith("[") or host.count(":") == 1:
                host = host.rsplit(":", 1)[0]
            return host.strip("[]").lower() in ("", "127.0.0.1", "localhost", "::1")

        def _redirect(self, location: str, cookie: str):
            self._drain()
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _desktop_login(self, token: str):
            with app.lock:  # kalit bir marta ishlaydi, lekin faqat to'g'ri kelganda kuyadi
                expected = app.desktop_token
                ok = bool(expected) and self._desktop() and hmac.compare_digest(token.encode(), expected.encode())
                if ok:
                    app.desktop_token = ""
            if not ok:
                raise Refused("Topilmadi.", 404)
            try:
                name = getpass.getuser()
            except Exception:
                name = ""
            self._redirect("/", self._cookie(store.new_session(store.local_user(name)), SESSION_DAYS * 86400))

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
                if not self._host_ok():
                    raise Refused("Topilmadi.", 404)
                if url.path == "/":
                    web_index = STATIC_DIR / "web" / "index.html"
                    if web_index.is_file():
                        return self._send(200, web_index.read_bytes(), "text/html; charset=utf-8")
                    return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
                if url.path.startswith("/assets/"):
                    web_root = (STATIC_DIR / "web").resolve()
                    asset = (web_root / url.path.lstrip("/")).resolve()
                    try:
                        asset.relative_to(web_root)
                    except ValueError:
                        raise Refused("Fayl topilmadi.", 404)
                    if not asset.is_file():
                        raise Refused("Fayl topilmadi.", 404)
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    return self._send(200, asset.read_bytes(), content_type)
                if url.path == "/manifest.webmanifest":
                    return self._send(200, MANIFEST, "application/manifest+json")
                if url.path in ICONS:
                    return self._send(200, (STATIC_DIR / url.path[1:]).read_bytes(), "image/png")
                if url.path == "/api/desktop-login":
                    return self._desktop_login(parse_qs(url.query).get("token", [""])[0])
                if url.path == "/api/me":
                    user_id, name = self._user()
                    local_desktop = self._desktop()
                    return self._json(200, {"user": name, "agents": app.agents(local_desktop), "chats": store.chats(user_id),
                                            "desktop": self._desktop()})
                if url.path == "/api/settings":
                    self._user()
                    cfg = config.read(app.config_file)
                    return self._json(200, {"lang": cfg.get("lang", "uz") if cfg.get("lang") in ("uz", "ru", "en") else "uz",
                                            "theme": cfg.get("theme", "dark") if cfg.get("theme") in ("dark", "light") else "dark",
                                            "accent": cfg.get("accent", "violet") if cfg.get("accent") in ("violet", "blue", "cyan", "emerald") else "violet"})
                if url.path == "/api/network":
                    self._user()
                    if not self._desktop():
                        raise Refused("Topilmadi.", 404)
                    return self._json(200, app.network_info())
                if url.path == "/api/network/users":
                    self._user()
                    if not self._desktop():
                        raise Refused("Topilmadi.", 404)
                    return self._json(200, {"users": store.employees()})
                if url.path == "/api/workspace":
                    self._user()
                    cfg = config.read(app.config_file)
                    local_desktop = self._desktop()
                    # Return metadata only: never expose MCP commands, headers, env vars, tokens or local paths.
                    mcp = ([{"name": str(x.get("name", "")), "transport": str(x.get("transport", "stdio")),
                             "enabled": bool(x.get("enabled", True))} for x in cfg.get("mcp", []) if isinstance(x, dict)]
                           if local_desktop else [])
                    discovered = skills.discover(cfg.get("project") or None) if local_desktop and cfg.get("skills", True) else []
                    project = (Path(cfg.get("project")).name if isinstance(cfg.get("project"), str)
                               and cfg.get("project") else "") if local_desktop else ""
                    return self._json(200, {"project": project, "plugins": mcp,
                                            "skills": [{"name": x.name, "description": x.description, "source": x.source}
                                                       for x in discovered],
                                            "automation": {"available": False, "reason": "Jadval va triggerlar moduli hali ulanmagan"},
                                            "database": {"engine": "SQLite", "status": "connected",
                                                         "users": len(store.users()), "chats": sum(
                                                             len(store.chats(uid)) for uid, in store._all("SELECT id FROM users"))}})
                if url.path == "/api/stream":
                    user_id, _ = self._user()
                    return self._stream(self._chat(user_id, parse_qs(url.query).get("chat", [""])[0]), self._desktop())
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
                if not self._host_ok():
                    raise Refused("Topilmadi.", 404)
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
                self.body_read = self.close_connection = True  # katta tanani o'qimaymiz: ulanish yopiladi
                raise Refused("Hajm juda katta.", 413)
            self.body_read = True
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
            if path == "/api/approve":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                app.resolve_approval(user_id, str(body.get("id", "")), str(body.get("answer", "")))
                return {"ok": True}, ""
            if path == "/api/desktop/classic":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                with app.lock:
                    if time.monotonic() - app.classic_at < 5:
                        raise Refused("Klassik oyna ochilmoqda, biroz kuting.", 429)
                    app.classic_at = time.monotonic()
                open_classic(app.config_file)
                return {"ok": True}, ""
            if path == "/api/settings":
                cfg = config.read(app.config_file)
                lang, theme, accent = body.get("lang", cfg.get("lang", "uz")), body.get("theme", cfg.get("theme", "dark")), body.get("accent", cfg.get("accent", "violet"))
                if lang not in ("uz", "ru", "en") or theme not in ("dark", "light") or accent not in ("violet", "blue", "cyan", "emerald"):
                    raise Refused("Sozlama qiymati noto'g'ri.")
                cfg.update({"lang": lang, "theme": theme, "accent": accent})
                config.write(cfg, app.config_file)
                return {"ok": True, "lang": lang, "theme": theme, "accent": accent}, ""
            if path == "/api/network":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                enabled = body.get("enabled")
                if not isinstance(enabled, bool):
                    raise Refused("Tarmoq serveri sozlamasi noto'g'ri.")
                try:
                    return app.set_network(enabled), ""
                except OSError as exc:
                    app.network_error = str(exc)
                    return app.network_info(), ""
            if path == "/api/network/users/action":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                try:
                    employee_id = int(body.get("id", 0))
                except (TypeError, ValueError):
                    raise Refused("Xodim hisobi topilmadi.")
                action = body.get("action")
                if action == "enable":
                    changed = store.set_employee_enabled(employee_id, True)
                elif action == "disable":
                    changed = store.set_employee_enabled(employee_id, False)
                elif action == "delete":
                    changed = store.remove_employee(employee_id)
                else:
                    raise Refused("Noto'g'ri amal.")
                if not changed:
                    raise Refused("Xodim hisobi topilmadi.", 404)
                return {"ok": True, "users": store.employees()}, ""
            if path == "/api/network/firewall":
                if not self._desktop() or not app.network_server:
                    raise Refused("Avval web-serverni yoqing.")
                ok, message = remote.open_firewall(app.network_server.server_port)
                return {"ok": ok, "message": message}, ""
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
                app.send(chat_id, str(body.get("text", "")), str(body.get("agent", "")), files,
                         local_desktop=self._desktop(), user_id=user_id)
            elif path == "/api/stop":
                app.stop(chat_id)
            else:
                raise Refused("Topilmadi.", 404)
            return {"ok": True}, ""

        def _file(self, chat_id: int, name: str, view: bool):
            """Agent shu suhbatda yaratgan fayl: yuklab beradi yoki (view) qum qutisidagi ko'rinish sahifasini beradi."""
            path = safe_file_path(app.files_dir(chat_id), name) or safe_file_path(app.uploads_dir(chat_id), name)
            if path is None:
                raise Refused("Fayl topilmadi.", 404)
            if path.stat().st_size > MAX_DOWNLOAD:
                raise Refused("Fayl 50 MB dan katta; uni kichikroq qismlarga ajrating.", 413)
            page = preview.page(path) if view else None
            if page is not None:
                return self._send(200, page.encode(), "text/html; charset=utf-8", csp=preview.CSP)
            ctype = FILE_TYPES.get(path.suffix.lower(), "application/octet-stream")  # .html faqat ko'rinishda ochiladi
            # Content-Disposition brauzerdagi download= atributidan ustun turadi, shuning uchun
            # biriktirmaning diskdagi vaqt belgisi emas, foydalanuvchi bergan nom yuboriladi.
            self._send(200, path.read_bytes(), ctype, download=shown_name(name))

        def _stream(self, chat_id: int, local_desktop: bool = False):
            """Suhbat hodisalari oqimi (SSE). Ulanish uzilguncha ochiq turadi."""
            q = app.subscribe(chat_id, local_desktop)
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
    app = App(store, config_file)
    httpd = Server((host, port), make_handler(app))
    httpd.store, httpd.app = store, app
    return httpd


_children: list = []  # ochilgan klassik oynalar: tugaganlari yig'ib turiladi


def open_classic(config_file: str | None = None) -> None:
    """Klassik (Tk) oynani alohida jarayonda ochadi: agentlar, API kalitlari va loyiha papkasi shu yerda sozlanadi."""
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "agent_umimiy"]
    cmd.append("--legacy-gui")
    if config_file:
        cmd += ["--config", str(config_file)]
    _children[:] = [child for child in _children if child.poll() is None]
    _children.append(subprocess.Popen(cmd, close_fds=True))


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
        httpd.app.shutdown()
        httpd.server_close()
        httpd.store.close()


def run_desktop(config_file: str | None = None) -> bool:
    """Dasturni o'z oynasida yangi interfeys bilan ochadi. Oyna ochilmasa False qaytaradi (klassik oynaga o'tish uchun).

    Server shu kompyuterga (127.0.0.1) ochiladi va oyna egasi bir martalik kalit bilan avtomatik kiradi.
    Sozlamalarda veb-server yoqilgan bo'lsa, lokal tarmoq uchun ham ochiladi: ular odatdagidek login bilan kiradi.
    """
    if not (STATIC_DIR / "web" / "index.html").is_file():
        return False
    try:
        import webview
    except Exception:
        return False
    cfg = config.read(config_file)
    host = "127.0.0.1"
    try:
        httpd = start(host, DESKTOP_PORT, config_file)
    except OSError:  # port band (masalan, dastur ikkinchi marta ochilgan): bo'sh portni tizim tanlaydi
        try:
            httpd = start(host, 0, config_file)
        except OSError:
            return False
    httpd.app.desktop, httpd.app.desktop_token = True, secrets.token_urlsafe(32)
    httpd.app.mcp_manager = mcplib.Manager(cfg.get("mcp", []))
    if cfg.get("server"):
        try:
            httpd.app.set_network(True)
        except OSError as exc:
            httpd.app.network_error = str(exc)
    port = httpd.server_port
    # Brauzer xotirasi (vazifalar ro'yxati) port bilan bog'liq: har bir port uchun alohida papka
    storage = config.user_dir() / ("webview" if port == DESKTOP_PORT else f"webview-{port}")
    width, height, maximized = 1440, 900, False
    try:  # oyna ekrandan katta bo'lib, chetlari ko'rinmay qolmasin (kichik noutbuklar)
        screen = webview.screens[0]
        width = min(width, max(880, screen.width - 60))
        height = min(height, max(560, screen.height - 90))  # vazifalar paneli va sarlavha uchun joy
        maximized = screen.width <= 1400 or screen.height <= 820  # kichik ekranda butun ekranga ochiladi
    except Exception:
        pass
    shown = threading.Event()
    icon_root = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
                 else Path(__file__).resolve().parent.parent / "packaging")
    icon_path = icon_root / "AgentUmimiy.ico"

    def on_shown(*_):
        shown.set()
        if sys.platform == "win32" and icon_path.is_file():
            def set_icon():
                try:
                    import ctypes
                    from ctypes import wintypes
                    user32 = ctypes.WinDLL("user32", use_last_error=True)
                    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    # Make Windows group the running window with the app's own pinned shortcut.
                    user32.LoadImageW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                                                  ctypes.c_int, ctypes.c_int, ctypes.c_uint)
                    user32.LoadImageW.restype = ctypes.c_void_p
                    hicon = user32.LoadImageW(None, str(icon_path.resolve()), 1, 0, 0, 0x10)
                    if hicon:
                        user32.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint,
                                                        ctypes.c_size_t, ctypes.c_ssize_t)
                        user32.SendMessageW.restype = ctypes.c_ssize_t
                        user32.SetClassLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
                        user32.SetClassLongPtrW.restype = ctypes.c_void_p
                        current_pid = kernel32.GetCurrentProcessId()
                        windows = []
                        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                        def collect(hwnd, _param):
                            owner = wintypes.DWORD()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                            if owner.value == current_pid and user32.IsWindowVisible(hwnd):
                                windows.append(hwnd)
                            return True
                        user32.EnumWindows(callback_type(collect), 0)
                        for hwnd in windows:
                            user32.SendMessageW(hwnd, 0x80, 0, hicon)  # WM_SETICON / small
                            user32.SendMessageW(hwnd, 0x80, 1, hicon)  # WM_SETICON / large
                            user32.SetClassLongPtrW(hwnd, -14, hicon)  # GCLP_HICON
                            user32.SetClassLongPtrW(hwnd, -34, hicon)  # GCLP_HICONSM
                except Exception:
                    pass
            threading.Timer(0.35, set_icon).start()

    try:
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AgentUmimiy.Desktop")
            except Exception:
                pass
        webview.create_window(
            "Agent Umimiy", f"http://127.0.0.1:{port}/api/desktop-login?token={httpd.app.desktop_token}",
            width=width, height=height, min_size=(880, 560), maximized=maximized, background_color="#04061a")
        webview.start(on_shown, private_mode=False, storage_path=str(storage))
    except Exception:
        if not shown.is_set():
            return False
    finally:
        httpd.app.shutdown()  # ishlayotgan agent javobi bazaga yozilib ulgursin
        stop(httpd)
    return shown.is_set()
