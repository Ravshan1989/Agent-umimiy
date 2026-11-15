"""Security & bug regression tests for RMS AI audit findings."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from agent_umimiy import automation, autostart, config, store, tools
from agent_umimiy.server import App, create
from agent_umimiy.telegram_bot import TelegramBridge


class _FakeMcpManager:
    def __init__(self, servers):
        self.servers = list(servers)
        self.configured = [list(servers)]
        self.shut_down = False

    def configure(self, servers):
        self.servers = list(servers)
        self.configured.append(list(servers))

    def shutdown(self):
        self.shut_down = True


class AuditSecurityTests(unittest.TestCase):
    def test_y1_remote_employee_does_not_get_admin_mcp_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "agents.json"
            cfg_file.write_text(
                json.dumps(
                    {
                        "agents": [{"name": "a1", "type": "echo", "enabled": True}],
                        "mcp": [{"name": "admin-fs", "command": "npx", "args": ["-y", "fs"]}],
                    }
                ),
                encoding="utf-8",
            )
            st = store.Store(Path(tmp) / "db.sqlite3")
            app = App(st, cfg_file)
            app.desktop = True
            app.mcp_manager = _FakeMcpManager([{"name": "admin-fs"}])
            try:
                owner_orch = app.orchestrator(local_desktop=True)
                self.assertIs(owner_orch.ctx.mcp, app.mcp_manager)
                self.assertTrue(owner_orch.ctx.allow_private)

                emp_orch = app.orchestrator(local_desktop=False)
                self.assertIsNone(emp_orch.ctx.mcp)
                self.assertFalse(emp_orch.ctx.allow_private)
            finally:
                app.shutdown()
                st.close()

    def test_y1_remote_employee_gets_only_web_users_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "agents.json"
            cfg_file.write_text(
                json.dumps(
                    {
                        "agents": [{"name": "a1", "type": "echo", "enabled": True}],
                        "mcp": [
                            {"name": "admin-fs", "command": "npx"},
                            {"name": "public-fetch", "command": "uvx", "web_users": True},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            st = store.Store(Path(tmp) / "db.sqlite3")
            app = App(st, cfg_file)
            app.desktop = True
            app.mcp_manager = _FakeMcpManager([])
            try:
                emp_orch = app.orchestrator(local_desktop=False)
                self.assertIsNotNone(emp_orch.ctx.mcp)
                self.assertIsNot(emp_orch.ctx.mcp, app.mcp_manager)
                self.assertEqual([s["name"] for s in emp_orch.ctx.mcp.servers], ["public-fetch"])
            finally:
                app.shutdown()
                st.close()

    def test_y2_network_server_and_employee_session_cannot_spoof_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "agents.json"
            config.write({"agents": []}, cfg_file)
            st = store.Store(Path(tmp) / "db.sqlite3")
            httpd = create(st, "127.0.0.1", 0, str(cfg_file))
            httpd.app.desktop = True
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                port = httpd.server_address[1]
                owner_id = httpd.store.local_user("owner")
                emp_id = httpd.store.add_user("employee1", "SecretPass123!")
                owner_tok = httpd.store.new_session(owner_id)
                emp_tok = httpd.store.new_session(emp_id)

                # Owner on desktop server -> desktop=True
                req_owner = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/me",
                    headers={"Cookie": f"session={owner_tok}"},
                )
                with urllib.request.urlopen(req_owner, timeout=5) as resp:
                    self.assertTrue(json.loads(resp.read().decode("utf-8")).get("desktop"))

                # Employee on desktop server -> desktop=False
                req_emp = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/me",
                    headers={"Cookie": f"session={emp_tok}"},
                )
                with urllib.request.urlopen(req_emp, timeout=5) as resp:
                    self.assertFalse(json.loads(resp.read().decode("utf-8")).get("desktop"))

                # Owner on network_server (is_desktop=False) -> desktop=False
                httpd.is_desktop = False
                with urllib.request.urlopen(req_owner, timeout=5) as resp:
                    self.assertFalse(json.loads(resp.read().decode("utf-8")).get("desktop"))
            finally:
                httpd.app.shutdown()
                httpd.shutdown()
                httpd.server_close()
                httpd.store.close()

    def test_y3_telegram_requires_allowed_username(self):
        bridge = TelegramBridge(lambda text: f"ok:{text}")
        info = bridge.configure("123:FAKE_TOKEN", "")
        self.assertEqual(info["status"], "xato")
        self.assertIn("majburiy", info["error"])

    def test_y4_autostart_requires_explicit_llm_root(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(autostart.ensure_local_services(), [])

    def test_o1_browser_open_blocks_private_ip_for_non_owner(self):
        ctx = tools.Context(root=Path.cwd(), allow_private=False)
        tb = tools.Toolbox(ctx, "t")
        out, err = tb.run("browser_open", {"url": "http://127.0.0.1:8080/admin"})
        self.assertTrue(err)
        self.assertIn("bloklangan", out)

    def test_n3_add_job_sets_created_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(automation, "_jobs_path", return_value=Path(tmp) / "automations.json"):
                job = automation.add_job("Test", "Say hi", interval_minutes=10)
                self.assertGreater(job["created_at"], 0)
                self.assertEqual(job["last_run"], 0)

    def test_x7_restore_migrates_legacy_db_missing_pinned_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_path = Path(tmp) / "legacy.sqlite3"
            conn = sqlite3.connect(str(legacy_path))
            conn.executescript(
                """
                CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, hash BLOB NOT NULL);
                CREATE TABLE chats (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL);
                CREATE TABLE records (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL);
                """
            )
            conn.commit()
            conn.close()
            raw = legacy_path.read_bytes()

            st = store.Store(Path(tmp) / "target.sqlite3")
            try:
                st.restore_bytes(raw)
                cols = {r[1] for r in st.db.execute("PRAGMA table_info(chats)").fetchall()}
                self.assertIn("pinned", cols)
            finally:
                st.close()


if __name__ == "__main__":
    unittest.main()
