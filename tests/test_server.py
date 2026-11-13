import base64
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from agent_umimiy import config, server
from agent_umimiy import store as store_module
from agent_umimiy.store import Store, StoreError

PASSWORD = "parol12345"


class Client:
    """Cookie'ni eslab qoladigan kichik HTTP mijoz."""

    def __init__(self, base: str):
        self.base, self.cookie = base, ""

    def call(self, path: str, body=None, ctype: str = "application/json"):
        headers = {"Cookie": self.cookie}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), ctype
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, headers=headers), timeout=10) as r:
                if r.headers.get("Set-Cookie"):
                    self.cookie = r.headers["Set-Cookie"].split(";")[0]
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def records(self, chat: int) -> list[dict]:
        """Agent ishini tugatguncha kutib, suhbatdagi barcha xabarlarni qaytaradi."""
        for _ in range(100):
            req = urllib.request.Request(f"{self.base}/api/stream?chat={chat}", headers={"Cookie": self.cookie})
            with urllib.request.urlopen(req, timeout=10) as r:
                init = json.loads(r.readline()[6:])  # birinchi hodisa: suhbatning to'liq holati
            if not init["busy"]:
                return init["records"]
            time.sleep(0.05)
        raise AssertionError("agent tugamadi")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        cfg = self.d / "agents.json"
        cfg.write_text(json.dumps({"web": False, "agents": [
            {"name": "aks", "type": "echo"}, {"name": "buyruq", "type": "cli", "command": "echo {prompt}"}]}))
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)
        self.store = Store(self.d / "server.db")
        self.httpd = server.create(self.store, config_file=str(cfg))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.store.close)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def user(self, name: str) -> Client:
        c = Client(self.base)
        code, _ = c.call("/api/register", {"name": name, "password": PASSWORD, "invite": self.store.invite().lower()})
        self.assertEqual(code, 200)
        return c

    def test_page_and_login_required(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"Agent Umimiy", r.read())
        c = Client(self.base)
        self.assertEqual(c.call("/api/me")[0], 401)
        self.assertEqual(c.call("/api/chat/new", {})[0], 401)

    def test_installable_as_phone_app(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b'rel="manifest" href="/manifest.webmanifest"', r.read())
        with urllib.request.urlopen(self.base + "/manifest.webmanifest") as r:
            manifest = json.loads(r.read())
        self.assertEqual((manifest["display"], manifest["start_url"]), ("standalone", "/"))
        for icon in [i["src"] for i in manifest["icons"]] + ["/apple-touch-icon.png"]:
            with urllib.request.urlopen(self.base + icon) as r:
                self.assertEqual((r.headers["Content-Type"], r.read()[:4]), ("image/png", b"\x89PNG"))

    def test_https_proxy_on_same_machine_is_trusted(self):
        def register(name, headers):
            req = urllib.request.Request(self.base + "/api/register", headers={"Content-Type": "application/json", **headers},
                                         data=json.dumps({"name": name, "password": PASSWORD, "invite": self.store.invite()}).encode())
            with urllib.request.urlopen(req) as r:
                return r.headers["Set-Cookie"]
        self.assertNotIn("Secure", register("Ali", {}))
        self.assertIn("; Secure", register("Vali", {"X-Forwarded-Proto": "https"}))

    def test_auto_agent_name_is_reserved(self):
        with self.assertRaisesRegex(ValueError, "nomi band"):
            config.build({"agents": [{"name": "auto", "type": "echo"}]})

    def test_register_needs_invite_and_login_checks_password(self):
        c = Client(self.base)
        self.assertEqual(c.call("/api/register", {"name": "Ali", "password": PASSWORD, "invite": "XATO"})[0], 403)
        self.user("Ali")
        self.assertEqual(self.store.users(), ["Ali"])
        code, body = Client(self.base).call("/api/register", {"name": "ali", "password": PASSWORD, "invite": self.store.invite()})
        self.assertEqual(code, 400, body)  # ism band
        self.assertEqual(Client(self.base).call("/api/login", {"name": "Ali", "password": "notogri-parol"})[0], 403)
        c = Client(self.base)
        self.assertEqual(c.call("/api/login", {"name": "ali", "password": PASSWORD})[0], 200)
        code, me = c.call("/api/me")
        self.assertEqual(me["agents"], [{"name": "auto", "model": "Avtomatik — o‘zi tanlaydi"},
                                        {"name": "aks", "model": ""}])  # CLI agent veb-foydalanuvchilarga berilmaydi
        self.assertEqual(c.call("/api/logout", {})[0], 200)
        self.assertEqual(c.call("/api/me")[0], 401)

    def test_memory_is_isolated_per_web_account(self):
        ali, vali = self.user("Ali"), self.user("Vali")
        saved = ali.call("/api/memory/remember", {"fact": "Ali maxsus ma'lumoti"})
        self.assertEqual(saved[0], 200)
        self.assertIn("saqlandi", saved[1]["message"].lower())
        ali_items = ali.call("/api/memory")[1]["items"]
        self.assertEqual(len(ali_items), 1)
        item_id = ali_items[0]["id"]
        self.assertEqual(vali.call("/api/memory")[1]["items"], [])
        # Vali Ali xotirasini ID orqali ham o'chira olmaydi.
        vali.call("/api/memory/delete", {"id": item_id})
        self.assertEqual(ali.call("/api/memory")[1]["items"], ali_items)
        ali.call("/api/memory/delete", {"id": item_id})
        self.assertEqual(ali.call("/api/memory")[1]["items"], [])

    def test_chat_stream_history_and_isolation(self):
        ali, vali = self.user("Ali"), self.user("Vali")
        chat = ali.call("/api/chat/new", {})[1]["id"]
        self.assertEqual(ali.call("/api/send", {"chat": chat, "text": "Salom", "agent": "aks"})[0], 200)
        self.assertEqual([(r["k"], r["text"]) for r in ali.records(chat)], [("user", "Salom"), ("agent", "[aks] Salom")])
        self.assertEqual(ali.call("/api/me")[1]["chats"], [{"id": chat, "title": "Salom"}])
        # ikkinchi savolda oldingi tarix agentga boradi va qayta ulanganda hamma xabar qaytadi
        ali.call("/api/send", {"chat": chat, "text": "Yana", "agent": "aks"})
        self.assertEqual(len(ali.records(chat)), 4)
        self.assertEqual([m["content"] for m in self.store.history(chat)], ["Salom", "[aks] Salom", "Yana", "[aks] Yana"])
        # boshqa foydalanuvchi bu suhbatni ko'rmaydi va unga yoza olmaydi
        self.assertEqual(vali.call("/api/me")[1]["chats"], [])
        self.assertEqual(vali.call(f"/api/stream?chat={chat}")[0], 404)
        self.assertEqual(vali.call("/api/send", {"chat": chat, "text": "x", "agent": "aks"})[0], 404)
        self.assertEqual(vali.call("/api/chat/delete", {"chat": chat})[0], 404)
        self.assertEqual(ali.call("/api/chat/delete", {"chat": chat})[0], 200)
        self.assertEqual(ali.call("/api/me")[1]["chats"], [])

    def test_attachment_and_bad_requests(self):
        ali = self.user("Ali")
        chat = ali.call("/api/chat/new", {})[1]["id"]
        note = {"name": "../eslatma.txt", "data": base64.b64encode(b"muhim matn").decode()}
        self.assertEqual(ali.call("/api/send", {"chat": chat, "text": "", "agent": "aks", "files": [note]})[0], 200)
        self.assertIn(".._eslatma.txt", ali.records(chat)[-1]["text"])
        self.assertEqual([p.parent for p in (self.d / "uploads").iterdir()], [self.d / "uploads"])
        self.assertEqual(ali.call("/api/send", {"chat": chat, "text": " ", "agent": "aks"})[0], 400)
        self.assertEqual(ali.call("/api/send", {"chat": chat, "text": "x", "agent": "buyruq"})[0], 400)
        self.assertEqual(ali.call("/api/chat/new", {}, ctype="text/plain")[0], 415)  # boshqa saytdagi forma

    def test_send_throttle_limits_each_user(self):
        throttle = server.Throttle()
        for _ in range(20):
            self.assertTrue(throttle.allow_send(10))
        self.assertFalse(throttle.allow_send(10))
        self.assertTrue(throttle.allow_send(11))

    def test_safe_file_path_rejects_symlink_escape(self):
        import os
        base = self.d / "chat-files"
        base.mkdir()
        outside = self.d / "secret.txt"
        outside.write_text("secret")
        link = base / "leak.txt"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink yaratish huquqi yo'q")
        self.assertIsNone(server.safe_file_path(base, "leak.txt"))
        self.assertIsNone(server.safe_file_path(base, "../secret.txt"))
        self.assertIsNone(server.safe_file_path(base, "missing.txt"))

    def test_web_input_limits_and_file_count(self):
        user_id = self.store.add_user("Ali", PASSWORD)
        chat = self.store.new_chat(user_id)
        app = server.App(self.store, str(self.d / "agents.json"))
        with self.assertRaises(server.Refused):
            app.send(chat, "x", "auto", [{}] * (server.MAX_FILES + 1))
        with self.assertRaises(server.Refused):
            app.send(chat, "x" * (server.MAX_PROMPT + 1), "auto", [])
        self.assertEqual(self.store.records(chat), [])

    def test_chat_records_are_capped(self):
        user_id = self.store.add_user("Ali", PASSWORD)
        chat = self.store.new_chat(user_id)
        with mock.patch.object(store_module, "MAX_RECORDS_PER_CHAT", 5):
            for i in range(8):
                self.store.add_record(chat, {"n": i})
        self.assertEqual([r["n"] for r in self.store.records(chat)], [3, 4, 5, 6, 7])

    def test_created_file_download_is_private(self):
        ali, vali = self.user("Ali"), self.user("Vali")
        chat = ali.call("/api/chat/new", {})[1]["id"]
        folder = self.d / "files" / str(chat)
        folder.mkdir(parents=True)
        (folder / "Ҳисобот 1.docx").write_bytes(b"PK-fayl")
        url = f"/api/file?chat={chat}&name=" + urllib.parse.quote("Ҳисобот 1.docx")
        req = urllib.request.Request(self.base + url, headers={"Cookie": ali.cookie})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.read(), b"PK-fayl")
            self.assertIn("attachment", r.headers["Content-Disposition"])
            self.assertIn("wordprocessingml", r.headers["Content-Type"])
        self.assertEqual(vali.call(url)[0], 404)  # begona suhbat
        # ko'rinish: HTML faqat qum qutisi siyosati bilan beriladi; Word uchun ko'rinish yo'q, u yuklab olinadi
        (folder / "sahifa.html").write_text("<script>document.title='x'</script>", encoding="utf-8")
        for name, sandboxed in (("sahifa.html", True), ("Ҳисобот 1.docx", False)):
            view = f"/api/file?chat={chat}&view=1&name=" + urllib.parse.quote(name)
            with urllib.request.urlopen(urllib.request.Request(self.base + view, headers={"Cookie": ali.cookie})) as r:
                self.assertEqual(r.headers["Content-Security-Policy"].startswith("sandbox "), sandboxed, name)
                self.assertEqual("attachment" in (r.headers["Content-Disposition"] or ""), not sandboxed, name)
        with urllib.request.urlopen(urllib.request.Request(  # view'siz HTML sahifa sifatida ochilmaydi
                self.base + f"/api/file?chat={chat}&name=sahifa.html", headers={"Cookie": ali.cookie})) as r:
            self.assertEqual((r.headers["Content-Type"], "attachment" in r.headers["Content-Disposition"]),
                             ("application/octet-stream", True))
        self.assertEqual(vali.call(f"/api/file?chat={chat}&view=1&name=sahifa.html")[0], 404)
        self.assertEqual(Client(self.base).call(url)[0], 401)
        for name in ("../server.db", "..%2Fserver.db", "yoq.docx", ""):
            self.assertEqual(ali.call(f"/api/file?chat={chat}&name={name}")[0], 404, name)
        self.assertEqual(ali.call("/api/chat/delete", {"chat": chat})[0], 200)
        self.assertFalse(folder.exists())  # suhbat bilan birga fayllari ham o'chadi

    def test_negative_content_length_is_rejected(self):
        # Noto'g'ri uzunlik rfile.read(-1) ga o'tib, so'rovni EOF gacha osiltirib qo'ymasligi kerak.
        class FakeRequest:
            headers = {"Content-Type": "application/json", "Content-Length": "-1"}
            close_connection = False
            def __init__(self):
                self.rfile = mock.Mock()
        handler = object.__new__(server.make_handler(server.App(self.store)))
        handler.headers = FakeRequest.headers
        handler.close_connection = False
        handler.rfile = mock.Mock()
        with self.assertRaises(server.Refused):
            handler._body()
        handler.rfile.read.assert_not_called()

    def test_oversized_content_length_is_rejected(self):
        handler = object.__new__(server.make_handler(server.App(self.store)))
        handler.headers = {"Content-Type": "application/json", "Content-Length": str(server.MAX_BODY + 1)}
        handler.close_connection = False
        handler.rfile = mock.Mock()
        with self.assertRaises(server.Refused) as caught:
            handler._body()
        self.assertEqual(caught.exception.code, 413)
        self.assertTrue(handler.close_connection)
        handler.rfile.read.assert_not_called()

    def test_wrong_passwords_get_locked_out(self):
        self.user("Ali")
        c = Client(self.base)
        codes = [c.call("/api/login", {"name": "Ali", "password": "xato-parol"})[0] for _ in range(21)]
        self.assertEqual((codes[0], codes[-1]), (403, 429))
        self.assertEqual(c.call("/api/login", {"name": "Ali", "password": PASSWORD})[0], 429)


class StoreTests(unittest.TestCase):
    def test_passwords_sessions_and_cascade(self):
        s = Store(":memory:")
        with self.assertRaises(StoreError):
            s.add_user("Ali", "qisqa")
        uid = s.add_user("Ali", PASSWORD)
        self.assertEqual((s.check_user("ALI", PASSWORD), s.check_user("Ali", "boshqa-parol")), (uid, None))
        token = s.new_session(uid)
        self.assertEqual(s.session_user(token), (uid, "Ali"))
        self.assertIsNone(s.session_user("soxta"))
        chat = s.new_chat(uid)
        s.add_record(chat, {"k": "user", "text": "x"})
        self.assertTrue(s.remove_user("ali"))
        self.assertEqual((s.session_user(token), s.records(chat)), (None, []))
        code = s.invite()
        self.assertEqual((len(code), s.invite()), (8, code))
        self.assertNotEqual(s.new_invite(), code)


if __name__ == "__main__":
    unittest.main()
