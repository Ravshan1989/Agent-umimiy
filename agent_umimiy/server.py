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
import socket
import socketserver
import subprocess
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import attachments, automation, config, discovery, memory, preview, rag, remote, skills, telegram_bot, translit
from . import mcp as mcplib
from .server_page import PAGE
from .store import SESSION_DAYS, Store, StoreError

MAX_BODY = 40 * 1024 * 1024
AUTH_BODY = 64 * 1024  # kirish/ro'yxatdan o'tish so'rovi uchun (sessiyasiz) yetarli hajm
OPEN_PATHS = ("/api/login", "/api/register", "/api/logout")  # sessiyasiz ham ochiq yo'llar
MAX_FILES = 6
MAX_PROMPT = 100_000
MAX_LIVE_TEXT = 200_000
SSE_QUEUE_SIZE = 256
MAX_CONNECTIONS = 256
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
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}
ICONS = {"/icon-192.png": 192, "/icon-512.png": 512, "/apple-touch-icon.png": 180}
# Telefonda «Bosh ekranga qo'shish» orqali ilova kabi ochilishi uchun (PWA)
MANIFEST = json.dumps({
    "name": "RMS AI", "short_name": "RMS AI", "lang": "uz", "start_url": "/", "scope": "/",
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
        self.web_mcp_manager = None
        self.network_server = None
        self.network_error = ""
        self.discovery: discovery.DiscoveryResponder | None = None
        self.desktop = False  # dastur o'z oynasida ishlayaptimi (run_desktop)
        self.desktop_token = ""  # oynani avtomatik kiritadigan bir martalik kalit
        self.client_key = secrets.token_urlsafe(24)  # AgentUmimiyClient ilovasi uchun kirish kaliti
        self.classic_at = 0.0  # klassik oyna oxirgi marta qachon ochilgani
        self.scheduler = automation.Scheduler(self.run_prompt_once)
        self.telegram = telegram_bot.TelegramBridge(lambda text: self.run_prompt_once(text, "auto"))

    def run_prompt_once(self, prompt: str, agent: str = "auto") -> str:
        orch = self.orchestrator(local_desktop=True)
        if agent == "auto" or agent not in orch.agents:
            res = orch.run(prompt, "auto")
        else:
            res = orch.run(prompt, "single", [agent])
        ok = next((r for r in reversed(res) if r.ok), res[-1] if res else None)
        return (ok.text if ok and ok.ok else (ok.error if ok else "Javob yo'q")) or "(bo'sh javob)"

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
            ctx.browser_private = True
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
            ctx.allow_private = False
            ctx.browser_private = False
            # Xotira, ko'nikmalar va admin MCP vositalari veb-foydalanuvchilarga berilmaydi
            ctx.memory = ctx.skills = False
            web_mcp = [m for m in cfg.get("mcp", []) if isinstance(m, dict) and m.get("web_users")]
            if web_mcp and self.mcp_manager:
                if not self.web_mcp_manager:
                    self.web_mcp_manager = type(self.mcp_manager)(web_mcp)
                else:
                    self.web_mcp_manager.configure(web_mcp)
                ctx.mcp = self.web_mcp_manager
            else:
                ctx.mcp = None
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
                "port": port, "invite": self.store.invite(), "client_key": self.client_key, "error": ""}

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
            server.is_desktop = False
            self.network_server = server
            self.network_error = ""
            cfg["server"] = True
            config.write(cfg, self.config_file)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                resp = discovery.DiscoveryResponder(port, client_key=self.client_key)
                resp.start()
                self.discovery = resp
            except OSError:
                pass
        else:
            server, self.network_server = self.network_server, None
            disc, self.discovery = self.discovery, None
            if disc:
                disc.stop()
            self.network_error = ""
            cfg["server"] = False
            config.write(cfg, self.config_file)
            if server:
                server.shutdown()
                server.server_close()
        return self.network_info()

    def agents(self, local_desktop: bool = False) -> list[dict]:
        return [{"name": "auto", "model": "Avtomatik — o‘zi tanlaydi"}] + [
            {"name": a.name, "model": a.options.get("model", ""), "description": a.description}
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
    PERSONAS = {
        "lawyer": "[Rol: Tajribali huquqshunos va shartnomalar eksperti. Hujjatlarni qonunchilik, huquqiy xavflar va manfaatlar nuqtai nazaridan aniq bandlar bilan tahlil qil.]\n\n",
        "accountant": "[Rol: Bosh buxgalter va moliyaviy tahlilchi. Raqamlar, soliq, foyda-zarar va hisob-kitoblarni aniq jadvallar bilan tekshir.]\n\n",
        "developer": "[Rol: Senior dasturchi va tizim arxitektori. Xavfsiz, tezkor va toza kod yoz hamda texnik yechim ber.]\n\n",
        "editor": "[Rol: Rasmiy ish yuritish muharriri va professional tarjimon (UZ/RU/EN). Matnlarni rasmiy hujjat uslubida bexato va ravon yoz.]\n\n",
    }
    STYLES = {
        "short": "[Javob uslubi: Juda qisqa, londa va faqat eng muhim 3-5 ta asosiy nuqta bilan javob ber.]\n\n",
        "detailed": "[Javob uslubi: Juda batafsil, chuqur tahlil, misollar va bosqichma-bosqich izohlar bilan javob ber.]\n\n",
        "table": "[Javob uslubi: Asosiy ma'lumot va taqqoslashlarni Markdown jadval (| Ustun | ... |) ko'rinishida taqdim et.]\n\n",
    }

    @staticmethod
    def _mask_pii(text: str) -> str:
        # Uzcard/Humo/Visa/Mastercard (16 raqam), JSHSHIR/PINFL (14 raqam), pasport va telefon raqamlarini yashiradi
        text = re.sub(r"\b(?:8600|9860|5614|4\d{3}|5\d{3})[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[KARTA_RAQAMI_YASHIRILDI]", text)
        text = re.sub(r"\b\d{14}\b", "[JSHSHIR_YASHIRILDI]", text)
        text = re.sub(r"\b[A-Z]{2}\s?\d{7}\b", "[PASPORT_YASHIRILDI]", text)
        text = re.sub(r"(?<!\d)(?:\+?998[\s-]?)\(?\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)", "[TELEFON_YASHIRILDI]", text)
        return text

    def send(self, chat_id: int, text: str, agent: str, files: list[dict],
             local_desktop: bool = False, user_id: int | None = None,
             persona: str = "", style: str = "", pii_guard: bool = False) -> None:
        if not isinstance(agent, str):
            raise Refused("Agent tanlovi noto'g'ri.")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise Refused("Fayllar ro'yxati noto'g'ri.")
        orch = self.orchestrator(local_desktop, chat_id, user_id)
        if agent not in ("auto", "broadcast", "pipeline", "consensus") and agent not in orch.agents:
            raise Refused("Bu agent mavjud emas. Sahifani yangilang.")
        orch.ctx.files_dir = str(self.files_dir(chat_id))
        if len(files) > MAX_FILES:
            raise Refused(f"Bir xabarda ko'pi bilan {MAX_FILES} ta fayl yuborish mumkin.")
        if not isinstance(text, str):
            raise Refused("Xabar matni noto'g'ri.")
        text = text.strip()
        if pii_guard and text:
            text = self._mask_pii(text)
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
                    att = attachments.save_upload(self.uploads_dir(chat_id), f.get("name", "fayl"), f.get("data", ""))
                    if pii_guard and att.text:
                        att.text = self._mask_pii(att.text)
                    atts.append(att)
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
            wiki_text = _read_wiki() if local_desktop else ""
            wiki_prefix = f"[Korxona ichki ma'lumotnomasi (Wiki):\n{wiki_text[:3000]}]\n\n" if wiki_text else ""
            model_prompt = wiki_prefix + self.PERSONAS.get(persona, "") + self.STYLES.get(style, "") + prompt
            threading.Thread(target=self._work, args=(chat_id, orch, model_prompt, agent, atts), daemon=True).start()
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
            elif agent in ("broadcast", "pipeline", "consensus"):
                targets = [a.name for a in orch.agents.values() if a.kind != "cli"] or list(orch.agents)
                results = orch.run(prompt, agent, targets, atts)
            else:
                results = orch.run(prompt, "single", [agent], atts)
            if agent not in ("auto", "broadcast", "pipeline", "consensus"):
                fallback = next((r.agent for r in reversed(results) if r.ok and r.agent != agent), "")
                if fallback:
                    self._publish(chat_id, {"type": "agent_changed", "agent": fallback})
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
        if self.web_mcp_manager:
            self.web_mcp_manager.shutdown()
            self.web_mcp_manager = None
        self.scheduler.stop()
        self.telegram.stop()
        network_server, self.network_server = self.network_server, None
        disc, self.discovery = self.discovery, None
        if disc:
            disc.stop()
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
        bp_root = config.user_dir() / "browser-profiles"
        if bp_root.is_dir():
            for bp in bp_root.glob(f"user-*-chat-{int(chat_id)}"):
                shutil.rmtree(bp, ignore_errors=True)


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


_STATIC_CACHE: dict[str, tuple[int, int, bytes]] = {}


def _export_chat(store: Store, chat_id: int, fmt: str) -> tuple[bytes, str, str]:
    """Suhbat tarixini .md, .docx, .pptx yoki .xlsx formatiga o'giradi."""
    import io
    raw_title = store.title(chat_id) or f"Suhbat-{chat_id}"
    safe_title = re.sub(r"[^\w\- ]+", "_", raw_title).strip()[:40] or f"suhbat-{chat_id}"
    recs = store.records(chat_id)
    if fmt == "docx":
        import docx
        doc = docx.Document()
        doc.add_heading(raw_title, level=1)
        for r in recs:
            if r.get("k") == "user":
                p = doc.add_paragraph()
                run = p.add_run("Siz: ")
                run.bold = True
                p.add_run(str(r.get("text") or ""))
            elif r.get("k") == "agent":
                name = str(r.get("name") or r.get("agent") or "Agent")
                meta = f" ({r['meta']})" if r.get("meta") else ""
                p = doc.add_paragraph()
                run = p.add_run(f"{name}{meta}: ")
                run.bold = True
                p.add_run(str(r.get("text") or ""))
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue(), FILE_TYPES[".docx"], f"{safe_title}.docx"
    if fmt == "pptx":
        import pptx
        prs = pptx.Presentation()
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        title_slide.shapes.title.text = raw_title
        if len(title_slide.placeholders) > 1:
            title_slide.placeholders[1].text = "RMS AI Platformasi hisoboti"
        pending_q = ""
        for r in recs:
            if r.get("k") == "user":
                pending_q = str(r.get("text") or "")[:120]
            elif r.get("k") == "agent":
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                name = str(r.get("name") or r.get("agent") or "Agent")
                slide.shapes.title.text = pending_q or f"{name} javobi"
                if len(slide.placeholders) > 1:
                    slide.placeholders[1].text = str(r.get("text") or "")[:1200]
                pending_q = ""
        buf = io.BytesIO()
        prs.save(buf)
        return buf.getvalue(), FILE_TYPES[".pptx"], f"{safe_title}.pptx"
    if fmt == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suhbat"
        ws.append(["Turi", "Muallif / Agent", "Vaqt / Holat", "Matn"])
        for r in recs:
            if r.get("k") == "user":
                ws.append(["Savol", "Siz", "", str(r.get("text") or "")])
            elif r.get("k") == "agent":
                ws.append(["Javob", str(r.get("name") or r.get("agent") or "Agent"), str(r.get("meta") or ""), str(r.get("text") or "")])
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue(), FILE_TYPES[".xlsx"], f"{safe_title}.xlsx"
    if fmt == "pdf":
        import textwrap

        from PIL import Image, ImageDraw, ImageFont
        pdf_font = None
        for font_name in (
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            if Path(font_name).is_file():
                try:
                    pdf_font = ImageFont.truetype(font_name, 14)
                    break
                except OSError:
                    pass
        if pdf_font is None:
            pdf_font = ImageFont.load_default()
        all_lines = [raw_title, "=" * min(60, len(raw_title)), ""]
        for r in recs:
            if r.get("k") == "user":
                all_lines.extend(textwrap.wrap(f"Siz: {r.get('text') or ''}", width=82) + [""])
            elif r.get("k") == "agent":
                name = str(r.get("name") or r.get("agent") or "Agent")
                for para in str(r.get("text") or "").splitlines() or [""]:
                    all_lines.extend(textwrap.wrap(f"{name}: {para}" if para == str(r.get("text") or "").splitlines()[0] else para, width=82) or [""])
                all_lines.append("")
        pages = []
        per_page = 48
        for idx in range(0, max(1, len(all_lines)), per_page):
            chunk = all_lines[idx:idx + per_page]
            img = Image.new("RGB", (794, 1123), "white")
            draw = ImageDraw.Draw(img)
            y = 44
            for line in chunk:
                draw.text((44, y), line, fill=(20, 24, 35), font=pdf_font)
                y += 20
            pages.append(img)
        buf = io.BytesIO()
        pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
        return buf.getvalue(), FILE_TYPES[".pdf"], f"{safe_title}.pdf"
    lines = [f"# {raw_title}\n"]
    for r in recs:
        if r.get("k") == "user":
            lines.append(f"### Siz\n\n{r.get('text') or ''}\n")
        elif r.get("k") == "agent":
            name = str(r.get("name") or r.get("agent") or "Agent")
            meta = f" *({r['meta']})*" if r.get("meta") else ""
            lines.append(f"### {name}{meta}\n\n{r.get('text') or ''}\n")
    return "\n".join(lines).encode("utf-8"), FILE_TYPES[".md"], f"{safe_title}.md"


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.12):
            return True
    except OSError:
        return False


def _system_health() -> dict:
    import os
    import platform
    try:
        usage = shutil.disk_usage(config.user_dir())
        free_gb = round(usage.free / (1024 ** 3), 1)
        total_gb = round(usage.total / (1024 ** 3), 1)
    except OSError:
        free_gb, total_gb = 0.0, 0.0
    return {
        "cpu_cores": os.cpu_count() or 1,
        "python": platform.python_version(),
        "disk_free_gb": free_gb,
        "disk_total_gb": total_gb,
        "ollama_online": _port_open(11434),
        "freellm_online": _port_open(3001),
    }


def _wiki_path() -> Path:
    return config.user_dir() / "wiki.md"


def _read_wiki() -> str:
    p = _wiki_path()
    try:
        return p.read_text(encoding="utf-8")[:15000] if p.is_file() else ""
    except OSError:
        return ""


def _write_wiki(text: str) -> str:
    p = _wiki_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cleaned = str(text or "")[:15000]
    p.write_text(cleaned, encoding="utf-8")
    return cleaned


def _project_audit(project_path: str | None) -> dict:
    if not project_path or not Path(project_path).is_dir():
        raise Refused("Avval Loyihalar bo'limida papka yo'lini biriktiring.")
    root = Path(project_path)
    counts: dict[str, int] = {}
    total_files = 0
    total_bytes = 0
    largest: list[tuple[int, str]] = []
    skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    for p in root.rglob("*"):
        if any(part in skip for part in p.parts):
            continue
        if p.is_file():
            try:
                sz = p.stat().st_size
            except OSError:
                continue
            total_files += 1
            total_bytes += sz
            ext = p.suffix.lower() or "(kengaytmasiz)"
            counts[ext] = counts.get(ext, 0) + 1
            rel = str(p.relative_to(root))
            largest.append((sz, rel))
    largest.sort(reverse=True)
    top_exts = [{"ext": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    top_files = [{"path": rel, "kb": round(sz / 1024, 1)} for sz, rel in largest[:8]]
    return {
        "root": str(root),
        "total_files": total_files,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "extensions": top_exts,
        "largest_files": top_files,
    }


def _export_zip(store: Store, user_id: int) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("database/agent-umimiy.sqlite3", store.backup_bytes())
        for fname in ("memory.json", "wiki.md", "automations.json"):
            fpath = config.user_dir() / fname
            if fpath.is_file():
                try:
                    zf.write(fpath, f"config/{fname}")
                except OSError:
                    pass
        for ch in store.chats(user_id):
            cid = ch["id"]
            data, _, filename = _export_chat(store, cid, "md")
            zf.writestr(f"chats/{cid}-{filename}", data)
    return buf.getvalue()


def _build_doc_template(chat_dir: Path, kind: str, org: str, partner: str, subject: str, amount: str) -> str:
    import docx
    chat_dir.mkdir(parents=True, exist_ok=True)
    org = org.strip() or "«KORXONA NOMI» MChJ"
    partner = partner.strip() or "«HAMKOR TASHKILOT» MChJ"
    subject = subject.strip() or "Xizmat ko'rsatish va mahsulot yetkazib berish"
    amount = amount.strip() or "10 000 000 (o'n million) so'm"
    today = time.strftime("%d.%m.%Y")
    titles = {
        "shartnoma": ("XIZMAT KO'RSATISH SHARTNOMASI", f"shartnoma_{int(time.time())}.docx"),
        "buyruq": ("KORXONA ICHKI BUYRUG'I", f"buyruq_{int(time.time())}.docx"),
        "ariza": ("RASMIY ARIZA", f"ariza_{int(time.time())}.docx"),
        "dalolatnoma": ("BAJARILGAN ISHLAR DALOLATNOMASI (AKT)", f"dalolatnoma_{int(time.time())}.docx"),
        "ishonchnoma": ("RASMIY ISHONCHNOMA", f"ishonchnoma_{int(time.time())}.docx"),
        "tijorat": ("TIJORAT TAKLIFI (KP)", f"tijorat_taklifi_{int(time.time())}.docx"),
    }
    heading, fname = titles.get(kind, titles["shartnoma"])
    doc = docx.Document()
    doc.add_heading(heading, 0)
    doc.add_paragraph(f"Sana: {today}-yil                                                  Toshkent sh.")
    if kind == "shartnoma":
        doc.add_paragraph(
            f"Mazkur shartnoma bir tomondan {org} («Buyurtmachi») va ikkinchi tomondan {partner} («Ijrochi») "
            f"o'rtasida quyidagilar haqida tuzildi:"
        )
        doc.add_heading("1. Shartnoma predmeti", level=2)
        doc.add_paragraph(f"1.1. Ijrochi Buyurtmachining topshirig'iga binoan «{subject}» bo'yicha ishlarni bajarish majburiyatini oladi.")
        doc.add_heading("2. Shartnoma summasi va hisob-kitob tartibi", level=2)
        doc.add_paragraph(f"2.1. Shartnomaning umumiy qiymati {amount} ni tashkil etadi.")
        doc.add_paragraph("2.2. To'lov bank o'tkazmasi orqali shartnoma imzolangandan so'ng amalga oshiriladi.")
        doc.add_heading("3. Tomonlarning javobgarligi va nizolarni hal etish", level=2)
        doc.add_paragraph("3.1. Tomonlar majburiyatlarni bajarmagan taqdirda O'zbekiston Respublikasi qonunchiligiga muvofiq javobgar bo'ladilar.")
    elif kind == "buyruq":
        doc.add_paragraph(f"Tashkilot: {org}")
        doc.add_heading(f"Mavzu: {subject} to'g'risida", level=2)
        doc.add_paragraph(f"BUYURAMAN:\n1. {subject} bo'yicha barcha tashkiliy ishlar {partner} zimmasiga yuklatilsin.")
        doc.add_paragraph("2. Mazkur buyruq ijrosini nazorat qilishni o'z zimmamda qoldiraman.")
    elif kind == "ariza":
        doc.add_paragraph(f"Kimga: {org} rahbariyatiga\nKimdan: {partner}")
        doc.add_paragraph(f"Mavzu: {subject}\n\nMen sizdan {subject} masalasida amaliy yordam berishingizni va zarur ruxsatnomani tasdiqlashingizni so'rayman.")
    elif kind == "dalolatnoma":
        doc.add_paragraph(f"Biz, quyida imzo chekuvchilar — {org} va {partner} vakillari ushbu dalolatnomani tuzdik:")
        doc.add_paragraph(f"1. «{subject}» bo'yicha barcha ishlar to'liq va sifatli bajarildi.")
        doc.add_paragraph(f"2. Bajarilgan ishlarning umumiy qiymati: {amount}. Tomonlarning bir-biriga e'tirozlari yo'q.")
    elif kind == "ishonchnoma":
        doc.add_paragraph(f"{org} ushbu ishonchnoma orqali {partner} ga «{subject}» bo'yicha hujjatlarni qabul qilish va imzolash vakolatini beradi.")
        doc.add_paragraph(f"Ishonchnoma {today}-yildan boshlab 1 (bir) yil muddatga amal qiladi.")
    else:
        doc.add_paragraph(f"Hurmatli {partner} rahbariyati!")
        doc.add_paragraph(f"{org} Sizga «{subject}» bo'yicha o'zining hamkorlik va tijorat taklifini taqdim etadi.")
        doc.add_paragraph(f"Taklif etilayotgan loyiha/xizmat qiymati: {amount}. Biz yuqori sifat va qisqa muddatlarni kafolatlaymiz.")
    doc.add_paragraph("\nTomonlar rekvizitlari va imzolari:")
    doc.add_paragraph(f"1-tomon: {org}  ____________________ (M.O'.)\n2-tomon: {partner}  ____________________ (M.O'.)")
    out = chat_dir / fname
    doc.save(str(out))
    return fname



def _read_static(path: Path) -> bytes:
    st = path.stat()
    key = str(path)
    hit = _STATIC_CACHE.get(key)
    if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
        return hit[2]
    data = path.read_bytes()
    if len(data) <= 8 * 1024 * 1024:
        _STATIC_CACHE[key] = (st.st_mtime_ns, st.st_size, data)
    return data


def make_handler(app: App):
    store, throttle = app.store, Throttle()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(30)  # sekin yuboriladigan so'rovlar server oqimini band qilmasin
            try:
                self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
        server_version = "AgentUmimiy"

        def handle_one_request(self):
            self.body_read = False  # har bir so'rov uchun qaytadan: ulanish keyingi so'rovga ham ishlatiladi
            self.drain_limit = MAX_BODY  # javobdan oldin bo'shatiladigan tananing eng katta hajmi
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
            if not str(raw).isascii() or not str(raw).isdecimal() or int(raw) > getattr(self, "drain_limit", MAX_BODY):
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
                  download: str = "", csp: str = PAGE_CSP, inline: bool = False):
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
                disposition = "inline" if inline else "attachment"
                self.send_header("Content-Disposition", f"{disposition}; filename*=UTF-8''{quote(download)}")
            if self.close_connection:  # tana o'qilmay qoldi: mijoz ulanish yopilishini oldindan bilsin
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj, cookie: str = ""):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), cookie=cookie)

        # ---- proksi ortida ----
        def _forwarded(self, header: str) -> str:
            """Proksi qo'shgan sarlavha; faqat so'rov shu kompyuterdagi proksidan kelganda ishoniladi."""
            if self.client_address[0] in ("127.0.0.1", "::1"):
                # eng o'ngdagi qiymatni proksining o'zi qo'shadi; chapdagilarni mijoz soxtalashtira oladi
                return self.headers.get(header, "").split(",")[-1].strip()
            return ""

        def _ip(self) -> str:
            return self._forwarded("X-Forwarded-For") or self.client_address[0]

        def _desktop(self) -> bool:
            """So'rov dasturning o'z oynasidan kelganmi: desktop serveri, shu kompyuter, proksisiz va egasining hisobi."""
            if not (getattr(self.server, "is_desktop", False) and app.desktop
                    and self.client_address[0] in ("127.0.0.1", "::1")
                    and not self.headers.get("X-Forwarded-For")):
                return False
            tok = self._token()
            if tok:
                user = store.session_user(tok)
                owner_id = store.local_user_id()
                if not user or (owner_id is not None and user[0] != owner_id):
                    return False
            return True

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

        def _client_allowed(self) -> bool:
            if self._desktop():
                return True
            if bool(config.read(app.config_file).get("web_access", True)):
                return True
            morsel = SimpleCookie(self.headers.get("Cookie", "")).get("au_client")
            return bool(morsel and hmac.compare_digest(morsel.value, app.client_key))

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
                if url.path == "/client-enter":
                    key = parse_qs(url.query).get("key", [""])[0]
                    if not key or not hmac.compare_digest(key, app.client_key):
                        raise Refused("Kirish ruxsati yo'q.", 403)
                    self.send_response(302)
                    self.send_header("Location", "/")
                    secure = "; Secure" if self._forwarded("X-Forwarded-Proto") == "https" else ""
                    self.send_header("Set-Cookie", f"au_client={app.client_key}; HttpOnly; SameSite=Strict; Path=/{secure}")
                    self.end_headers()
                    return None
                if not self._client_allowed():
                    msg = (
                        "<!doctype html><html lang='uz'><meta charset='utf-8'>"
                        "<body style='font-family:Segoe UI,sans-serif;background:#0b101b;color:#e6edf7;"
                        "display:grid;place-items:center;min-height:100vh;margin:0'>"
                        "<div style='max-width:440px;padding:24px;border-radius:14px;background:#141d2e;"
                        "border:1px solid rgba(148,163,184,.25)'>"
                        "<h2 style='margin:0 0 8px'>Veb-brauzer orqali kirish yopiq</h2>"
                        "<p style='margin:0;color:#9fb0c7;line-height:1.5'>Faqat <b>RMS AI Client</b> "
                        "desktop ilovasi orqali ulanish mumkin (yoki admindan veb-ruxsat so‘rang).</p>"
                        "</div></body></html>"
                    )
                    if url.path.startswith("/api/"):
                        return self._json(403, {"error": "Veb-brauzer orqali kirish yopiq."})
                    return self._send(403, msg.encode("utf-8"), "text/html; charset=utf-8")
                if url.path == "/":
                    web_index = STATIC_DIR / "web" / "index.html"
                    if web_index.is_file():
                        return self._send(200, _read_static(web_index), "text/html; charset=utf-8")
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
                    return self._send(200, _read_static(asset), content_type)
                if url.path == "/manifest.webmanifest":
                    return self._send(200, MANIFEST, "application/manifest+json")
                if url.path in ICONS:
                    return self._send(200, _read_static(STATIC_DIR / url.path[1:]), "image/png")
                if url.path == "/api/desktop-login":
                    return self._desktop_login(parse_qs(url.query).get("token", [""])[0])
                if url.path == "/api/me":
                    user_id, name = self._user()
                    local_desktop = self._desktop()
                    return self._json(200, {"user": name, "agents": app.agents(local_desktop), "chats": store.chats(user_id),
                                            "desktop": self._desktop()})
                if url.path == "/api/settings":
                    uid, _ = self._user()
                    cfg = config.read(app.config_file)
                    prefs = cfg if self._desktop() else (cfg.get("user_settings") or {}).get(str(uid), cfg)
                    lang = prefs.get("lang", cfg.get("lang", "uz"))
                    theme = prefs.get("theme", cfg.get("theme", "dark"))
                    accent = prefs.get("accent", cfg.get("accent", "violet"))
                    return self._json(200, {"lang": lang if lang in ("uz", "uz_cyrl", "ru", "en") else "uz",
                                            "theme": theme if theme in ("dark", "light") else "dark",
                                            "accent": accent if accent in ("violet", "blue", "cyan", "emerald") else "violet"})
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
                    user_id, _ = self._user()
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
                                            "automation": {"available": local_desktop,
                                                           "reason": "Jadval va triggerlar moduli faol" if local_desktop else "Faqat desktop oynasida mavjud",
                                                           "jobs": automation.list_jobs() if local_desktop else []},
                                            "rag": rag.stats() if local_desktop else {"indexed": 0},
                                            "telegram": app.telegram.info() if local_desktop else {"enabled": False, "status": "o'chiq", "bot_username": "", "allowed_username": "", "error": ""},
                                            "memory": memory.list_all() if local_desktop else [],
                                            "wiki": _read_wiki() if local_desktop else "",
                                            "system": _system_health() if local_desktop else {},
                                            "analytics": store.analytics(user_id),
                                            "database": {"engine": "SQLite", "status": "connected",
                                                         "users": store.user_count() if local_desktop else None,
                                                         "chats": store.chat_count() if local_desktop else None}})
                if url.path == "/api/chat/export":
                    user_id, _ = self._user()
                    query = parse_qs(url.query)
                    chat_id = self._chat(user_id, query.get("chat", [""])[0])
                    fmt = query.get("format", ["md"])[0].lower()
                    if fmt not in ("md", "docx", "pptx", "xlsx", "pdf"):
                        raise Refused("Format noto'g'ri.")
                    data, ctype, filename = _export_chat(store, chat_id, fmt)
                    return self._send(200, data, ctype, download=filename)
                if url.path == "/api/qr":
                    self._user()
                    import io

                    import qrcode
                    text = parse_qs(url.query).get("text", [""])[0][:1500] or "RMS AI"
                    img = qrcode.make(text)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    return self._send(200, buf.getvalue(), "image/png", inline=True)
                if url.path == "/api/chat/search":
                    user_id, _ = self._user()
                    q = parse_qs(url.query).get("q", [""])[0]
                    return self._json(200, {"ids": store.search_chats(user_id, q)})
                if url.path == "/api/desktop/backup":
                    self._user()
                    if not self._desktop():
                        raise Refused("Topilmadi.", 404)
                    stamp = time.strftime("%Y%m%d-%H%M%S")
                    return self._send(200, store.backup_bytes(), "application/octet-stream",
                                      download=f"agent-umimiy-backup-{stamp}.sqlite3")
                if url.path == "/api/desktop/export-zip":
                    user_id, _ = self._user()
                    if not self._desktop():
                        raise Refused("Topilmadi.", 404)
                    stamp = time.strftime("%Y%m%d-%H%M%S")
                    return self._send(200, _export_zip(store, user_id), "application/zip",
                                      download=f"agent-umimiy-full-archive-{stamp}.zip")
                if url.path == "/api/stream":
                    user_id, _ = self._user()
                    return self._stream(self._chat(user_id, parse_qs(url.query).get("chat", [""])[0]), self._desktop())
                if url.path == "/api/file":
                    user_id, _ = self._user()
                    query = parse_qs(url.query)
                    return self._file(self._chat(user_id, query.get("chat", [""])[0]), query.get("name", [""])[0],
                                      bool(query.get("view")), bool(query.get("inline")))
                raise Refused("Topilmadi.", 404)
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})
            except Exception:
                self._json(500, {"error": "Ichki server xatoligi."})

        def do_POST(self):
            path = urlparse(self.path).path
            # Sessiyasiz so'rovda faqat kichik tana bo'shatiladi; kattasida ulanish yopiladi
            self.drain_limit = AUTH_BODY
            try:
                if not self._host_ok():
                    raise Refused("Topilmadi.", 404)
                if not self._client_allowed():
                    raise Refused("Veb-brauzer orqali kirish yopiq. Faqat RMS AI Client ilovasi orqali ulanish mumkin.", 403)
                if path not in OPEN_PATHS:
                    self._user()  # 40 MB tanani o'qishdan oldin sessiya tekshiriladi
                    self.drain_limit = MAX_BODY
                self._json(200, *self._post(path, self._body(MAX_BODY if path not in OPEN_PATHS else AUTH_BODY)))
            except Refused as exc:
                self._json(exc.code, {"error": str(exc)})
            except StoreError as exc:
                self._json(400, {"error": str(exc)})
            except Exception:
                self._json(500, {"error": "Ichki server xatoligi. Qayta urinib ko'ring."})

        def _body(self, limit: int = MAX_BODY) -> dict:
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
            if size > limit:
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
                    invite = str(body.get("invite", "")).strip().upper()
                    if not hmac.compare_digest(invite, store.invite()):
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
                prefs = cfg if self._desktop() else (cfg.get("user_settings") or {}).get(str(user_id), cfg)
                lang = body.get("lang", prefs.get("lang", cfg.get("lang", "uz")))
                theme = body.get("theme", prefs.get("theme", cfg.get("theme", "dark")))
                accent = body.get("accent", prefs.get("accent", cfg.get("accent", "violet")))
                if lang not in ("uz", "uz_cyrl", "ru", "en") or theme not in ("dark", "light") or accent not in ("violet", "blue", "cyan", "emerald"):
                    raise Refused("Sozlama qiymati noto'g'ri.")
                if self._desktop():
                    cfg.update({"lang": lang, "theme": theme, "accent": accent})
                else:
                    cfg.setdefault("user_settings", {})[str(user_id)] = {"lang": lang, "theme": theme, "accent": accent}
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
                    emp_chats = [c["id"] for c in store.chats(employee_id)]
                    changed = store.remove_employee(employee_id)
                    if changed:
                        for cid in emp_chats:
                            shutil.rmtree(app.files_dir(cid), ignore_errors=True)
                            shutil.rmtree(
                                config.user_dir() / "browser-profiles" / f"user-{employee_id}-chat-{cid}",
                                ignore_errors=True,
                            )
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
            if path == "/api/automation":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                act = str(body.get("action", ""))
                try:
                    if act == "add":
                        automation.add_job(
                            str(body.get("title", "")),
                            str(body.get("prompt", "")),
                            str(body.get("agent", "auto")),
                            int(body.get("interval_minutes", 60)),
                        )
                        jobs = automation.list_jobs()
                    elif act == "run":
                        jobs = automation.run_job_now(int(body.get("id", 0)), app.run_prompt_once)
                    elif act == "toggle":
                        jobs = automation.toggle_job(int(body.get("id", 0)))
                    elif act == "delete":
                        jobs = automation.delete_job(int(body.get("id", 0)))
                    else:
                        raise Refused("Noto'g'ri amal.")
                except (ValueError, TypeError) as exc:
                    raise Refused(str(exc))
                return {"ok": True, "jobs": jobs}, ""
            if path == "/api/desktop/agents":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                act = str(body.get("action", ""))
                cfg = config.read(app.config_file)
                items = [a for a in cfg.get("agents", []) if isinstance(a, dict)]
                if act == "add":
                    name = re.sub(r"[^A-Za-z0-9_.:-]", "-", str(body.get("name", "")).strip())[:48]
                    kind = str(body.get("type", "openai")).strip()
                    if not name or kind not in ("openai", "ollama", "anthropic", "gemini"):
                        raise Refused("Agent nomi va turi to'g'ri kiritilishi kerak.")
                    entry = {
                        "name": name,
                        "type": kind,
                        "model": str(body.get("model", "")).strip() or "auto",
                        "description": str(body.get("description", "")).strip()[:160],
                        "enabled": True,
                        "tools": False,
                    }
                    if body.get("base_url"):
                        entry["base_url"] = str(body["base_url"]).strip()
                    if body.get("api_key"):
                        entry["api_key"] = str(body["api_key"]).strip()
                    items = [a for a in items if a.get("name") != name] + [entry]
                    cfg["agents"] = items[:16]
                    config.write(cfg, app.config_file)
                elif act == "delete":
                    name = str(body.get("name", "")).strip()
                    cfg["agents"] = [a for a in items if a.get("name") != name]
                    config.write(cfg, app.config_file)
                else:
                    raise Refused("Noto'g'ri amal.")
                return {"ok": True, "agents": app.agents(True)}, ""
            if path == "/api/desktop/rag":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                act = str(body.get("action", ""))
                cfg = config.read(app.config_file)
                if act == "index":
                    if body.get("project"):
                        proj = str(body["project"]).strip()
                        if not Path(proj).is_dir():
                            raise Refused("Bunday papka topilmadi.")
                        cfg["project"] = proj
                        config.write(cfg, app.config_file)
                    info = rag.index_project(cfg.get("project"))
                    return {"ok": True, **info}, ""
                if act == "search":
                    return {"ok": True, "results": rag.search(str(body.get("query", "")))}, ""
                if act == "audit":
                    return {"ok": True, "audit": _project_audit(cfg.get("project"))}, ""
                raise Refused("Noto'g'ri amal.")
            if path == "/api/desktop/wiki":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                saved = _write_wiki(str(body.get("wiki", "")))
                return {"ok": True, "wiki": saved}, ""
            if path == "/api/desktop/restore":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                import base64
                raw_b64 = str(body.get("data", ""))
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                try:
                    raw_bytes = base64.b64decode(raw_b64)
                except Exception:
                    raise Refused("Fayl formati noto'g'ri.")
                store.restore_bytes(raw_bytes)
                new_uid = store.local_user(getpass.getuser())
                cookie = self._cookie(store.new_session(new_uid), SESSION_DAYS * 86400)
                return {"ok": True, "chats": store.chats(new_uid)}, cookie
            if path == "/api/desktop/telegram":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                cfg = config.read(app.config_file)
                token = str(body.get("token", "")).strip()
                allowed = str(body.get("allowed_username", "")).strip().lstrip("@")
                cfg["telegram_token"] = token
                cfg["telegram_user"] = allowed
                config.write(cfg, app.config_file)
                return {"ok": True, "telegram": app.telegram.configure(token, allowed)}, ""
            if path == "/api/desktop/screenshot":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                try:
                    import base64
                    import io

                    from PIL import ImageGrab
                    img = ImageGrab.grab()
                    img.thumbnail((1920, 1080))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    return {"ok": True, "name": f"ekran_{int(time.time())}.png", "data": b64}, ""
                except Exception as exc:
                    raise Refused(f"Ekran rasmini olib bo'lmadi: {exc}")
            if path == "/api/desktop/memory":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                act = str(body.get("action", "list"))
                msg = ""
                if act == "add":
                    msg = memory.remember(str(body.get("fact", "")))
                elif act == "delete":
                    msg = memory.forget(str(body.get("id", "")))
                return {"ok": True, "memory": memory.list_all(), "message": msg}, ""
            if path == "/api/desktop/run-code":
                if not self._desktop():
                    raise Refused("Topilmadi.", 404)
                code = str(body.get("code", ""))
                if not code.strip() or len(code) > 20000:
                    raise Refused("Kod bo'sh yoki juda uzun.")
                py_bin = sys.executable
                if getattr(sys, "frozen", False):
                    py_bin = shutil.which("python") or shutil.which("python3") or shutil.which("py") or ""
                    if not py_bin:
                        raise Refused("Yig'ilgan dasturda kodni bajarish uchun tizim Python'i topilmadi.")
                try:
                    proc = subprocess.run(
                        [py_bin, "-c", code],
                        capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
                    )
                    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
                    return {"ok": proc.returncode == 0, "output": (out.strip() or "(bo'sh natija)")[:8000]}, ""
                except subprocess.TimeoutExpired:
                    raise Refused("Kod bajarilishi 10 soniyadan oshib ketdi (Timeout).")
                except Exception as exc:
                    raise Refused(f"Kod bajarishda xato: {exc}")
            if path == "/api/translit":
                text = str(body.get("text", ""))[:50000]
                target = str(body.get("target", "auto"))
                return {"ok": True, "text": translit.convert(text, target)}, ""
            if path == "/api/chat/new":
                if len(store.chats(user_id)) >= 100:
                    raise Refused("Bir foydalanuvchi ko'pi bilan 100 ta suhbat yaratishi mumkin.", 429)
                return {"id": store.new_chat(user_id)}, ""
            chat_id = self._chat(user_id, body.get("chat"))
            if path == "/api/chat/fork":
                if len(store.chats(user_id)) >= 100:
                    raise Refused("Bir foydalanuvchi ko'pi bilan 100 ta suhbat yaratishi mumkin.", 429)
                new_id = store.fork_chat(user_id, chat_id)
                return {"ok": True, "id": new_id, "chats": store.chats(user_id)}, ""
            if path == "/api/doc-template":
                kind = str(body.get("kind", "shartnoma")).strip().lower()
                org = str(body.get("org", ""))
                partner = str(body.get("partner", ""))
                subject = str(body.get("subject", ""))
                amount = str(body.get("amount", ""))
                fname = _build_doc_template(app.files_dir(chat_id), kind, org, partner, subject, amount)
                app._record(chat_id, {"k": "act", "agent": "Hujjat Generator", "kind": "file", "text": fname})
                app._record(chat_id, {"k": "agent", "name": "Hujjat Generator",
                                      "text": f"Rasmiy **{kind.upper()}** hujjati tayyorlandi: `{fname}`. Yuqoridagi fayl tugmasi orqali Word (.docx) formatida yuklab olishingiz mumkin.",
                                      "meta": "tayyor"})
                return {"ok": True, "file": fname}, ""
            if path == "/api/chat/pin":
                pinned = store.toggle_pin(user_id, chat_id)
                return {"ok": True, "pinned": pinned, "chats": store.chats(user_id)}, ""
            if path == "/api/chat/rename":
                title = str(body.get("title", "")).strip().replace("\n", " ")[:TITLE_LEN]
                if not title:
                    raise Refused("Suhbat nomi bo'sh bo'lmasin.")
                store.set_title(chat_id, title)
                return {"ok": True, "chats": store.chats(user_id)}, ""
            if path == "/api/chat/clear":
                with app.lock:
                    ch = app.channels.get(chat_id)
                    if ch and ch.busy:
                        raise Refused("Agent hali ishlayapti. Avval to'xtating.")
                store.clear_chat(chat_id)
                return {"ok": True}, ""
            if path == "/api/chat/delete":
                app.delete_chat(chat_id)
            elif path == "/api/send":
                if not throttle.allow_send(user_id):
                    raise Refused("Yuborish limiti: 60 soniyada 20 ta xabar. Biroz kuting.", 429)
                files = body.get("files") or []
                if not isinstance(files, list) or not all(isinstance(f, dict) for f in files):
                    raise Refused("Noto'g'ri so'rov.")
                app.send(chat_id, str(body.get("text", "")), str(body.get("agent", "")), files,
                         local_desktop=self._desktop(), user_id=user_id,
                         persona=str(body.get("persona", "")),
                         style=str(body.get("style", "")),
                         pii_guard=bool(body.get("pii_guard", False)))
            elif path == "/api/stop":
                app.stop(chat_id)
            else:
                raise Refused("Topilmadi.", 404)
            return {"ok": True}, ""

        def _file(self, chat_id: int, name: str, view: bool, inline: bool = False):
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
            is_image = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
            self._send(200, path.read_bytes(), ctype, download=shown_name(name), inline=inline and is_image)

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
    allow_reuse_address = sys.platform != "win32"
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
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def create(store: Store, host: str = "127.0.0.1", port: int = 0, config_file: str | None = None) -> Server:
    app = App(store, config_file)
    httpd = Server((host, port), make_handler(app))
    httpd.store, httpd.app = store, app
    httpd.is_desktop = host in ("127.0.0.1", "::1")
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
    disc = None
    if host == "0.0.0.0":
        try:
            disc = discovery.DiscoveryResponder(httpd.server_port, client_key=httpd.app.client_key)
            disc.start()
        except OSError:
            disc = None
    print("RMS AI veb-server ishga tushdi. Brauzerda oching:")
    for url in urls(httpd):
        print("  " + url)
    print(f"Ro'yxatdan o'tish uchun taklif kodi: {httpd.store.invite()}")
    print("To'xtatish: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if disc:
            disc.stop()
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
    httpd.app.scheduler.start()
    if cfg.get("telegram_token"):
        threading.Thread(
            target=httpd.app.telegram.configure,
            args=(str(cfg.get("telegram_token", "")), str(cfg.get("telegram_user", ""))),
            daemon=True,
        ).start()
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
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RMSAI.Desktop")
            except Exception:
                pass
        webview.create_window(
            "RMS AI", f"http://127.0.0.1:{port}/api/desktop-login?token={httpd.app.desktop_token}",
            width=width, height=height, min_size=(880, 560), maximized=maximized, background_color="#04061a")
        webview.start(on_shown, private_mode=False, storage_path=str(storage))
    except Exception:
        if not shown.is_set():
            return False
    finally:
        httpd.app.shutdown()  # ishlayotgan agent javobi bazaga yozilib ulgursin
        stop(httpd)
    return shown.is_set()
