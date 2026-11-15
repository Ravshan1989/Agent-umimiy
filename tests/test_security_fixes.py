"""Security regression tests for RMS AI audit fixes (Y1, Y2, Y3, Y4, O1)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from agent_umimiy import autostart, config, store, tools
from agent_umimiy.server import App, start
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


class SecurityFixesTest(unittest.TestCase):
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

                emp_orch = app.orchestrator(local_desktop=False)
                self.assertIsNone(emp_orch.ctx.mcp)
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

    def test_y2_network_server_cannot_spoof_desktop_from_localhost(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "agents.json"
            config.write({"agents": []}, cfg_file)
            httpd = start("127.0.0.1", 0, str(cfg_file))
            httpd.app.desktop = True
            try:
                port = httpd.server_address[1]
                tok = httpd.store.new_session(httpd.store.local_user("test"))
                req1 = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/me",
                    headers={"Cookie": f"session={tok}"},
                )
                with urllib.request.urlopen(req1, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data.get("desktop"))

                httpd.is_desktop = False
                req2 = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/me",
                    headers={"Cookie": f"session={tok}"},
                )
                with urllib.request.urlopen(req2, timeout=5) as resp:
                    data2 = json.loads(resp.read().decode("utf-8"))
                self.assertFalse(data2.get("desktop"))
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


if __name__ == "__main__":
    unittest.main()
