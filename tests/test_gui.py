"""Oynaning tutun sinovi: haqiqiy Tk oynasi ochiladi (ekran bo'lmasa o'tkazib yuboriladi; CI'da xvfb ostida ishlaydi)."""
import json
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from agent_umimiy import config

try:
    import tkinter as tk

    from agent_umimiy import gui
    _probe = tk.Tk()
    _probe.destroy()
    SKIP = ""
except Exception as exc:  # tkinter o'rnatilmagan yoki ekran yo'q
    SKIP = f"oyna ochib bo'lmaydi: {exc}"


@unittest.skipIf(SKIP, SKIP)
class GuiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.cfg = self.d / "agents.json"
        self.cfg.write_text(json.dumps({"agents": [{"name": "aks", "type": "echo"}], "web": False, "server_port": 0}))
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)
        self.app = gui.App(str(self.cfg))
        self.addCleanup(self._close)
        self.app.update()

    def _close(self):
        if self.app.winfo_exists():
            self.app._on_close()

    def pump(self, until, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            self.app.update()
            if until():
                return
            time.sleep(0.02)
        self.fail("kutilgan holat yuz bermadi")

    def test_send_shows_answer(self):
        chat = self.app.cur
        self.app._dispatch(chat, "Salom", [])
        self.pump(lambda: not chat.busy)
        self.assertEqual([(r["k"], r["text"]) for r in chat.records], [("user", "Salom"), ("agent", "[aks] Salom")])

    def test_streamed_text_is_shown_live_then_replaced(self):
        chat = self.app.cur
        chat.busy = True
        for kind, text in (("delta", "Sal"), ("delta", "om"), ("read", "fayl o'qildi")):
            self.app.inbox.put(("event", chat, "aks", kind, text))
        self.app._poll()
        self.app.update()
        self.assertEqual(chat.live["aks"].body.cget("text"), "Salom")
        self.assertEqual([r["k"] for r in chat.records], ["act"])  # oqim bo'laklari tarixga yozilmaydi
        self.app.inbox.put(("event", chat, "aks", "turn", ""))
        self.app._poll()
        self.assertEqual(chat.live, {})
        self.app.inbox.put(("event", chat, "aks", "delta", "Yangi"))
        self.app.inbox.put(("done", chat, [], ""))
        self.app._poll()
        self.assertEqual((chat.live, chat.stream, chat.busy), ({}, {}, False))

    def test_created_file_gets_a_clickable_row(self):
        chat = self.app.cur
        self.app.inbox.put(("event", chat, "aks", "file", str(self.d / "hisobot.xlsx")))
        self.app._poll()
        self.app.update()
        self.assertEqual(chat.records[-1], {"k": "act", "agent": "aks", "kind": "file", "text": str(self.d / "hisobot.xlsx")})
        texts = [w.cget("text") for row in chat.inner.winfo_children() for w in row.winfo_children() if isinstance(w, tk.Label)]
        self.assertTrue(any("hisobot.xlsx" in t for t in texts), texts)
        self.assertEqual(Path(chat.orch.ctx.files_dir).name, "Agent Umimiy")

    def test_web_server_toggle_and_autostart_setting(self):
        self.assertIsNone(self.app.web_server)
        dialog = gui.ServerDialog(self.app)
        dialog._toggle()
        self.app.update()
        httpd = self.app.web_server
        self.assertTrue(json.loads(self.cfg.read_text())["server"])  # keyingi ochilishda o'zi yoqiladi
        self.assertEqual(dialog.invite_var.get(), httpd.store.invite())
        with urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_port}/manifest.webmanifest", timeout=5) as r:
            self.assertEqual(r.status, 200)
        dialog._toggle()
        self.assertIsNone(self.app.web_server)
        self.assertFalse(json.loads(self.cfg.read_text())["server"])
        dialog.destroy()

    def test_server_starts_with_the_app_when_enabled(self):
        self._close()
        self.cfg.write_text(json.dumps({"agents": [{"name": "aks", "type": "echo"}], "server": True, "server_port": 0}))
        self.app = gui.App(str(self.cfg))
        self.pump(lambda: self.app.web_server is not None)
        with urllib.request.urlopen(f"http://127.0.0.1:{self.app.web_server.server_port}/", timeout=5) as r:
            self.assertIn(b"Agent Umimiy", r.read())


if __name__ == "__main__":
    unittest.main()
