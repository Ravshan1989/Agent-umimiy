import http.client
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from agent_umimiy import config, server, tools
from agent_umimiy.store import Store


def _link_dir(link: Path, target: Path) -> bool:
    """Papkaga symlink, bo'lmasa (Windows) junction yaratadi; imkon bo'lmasa False."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
        return True
    except (ImportError, OSError, AttributeError):
        return False


class SearchFilesEscapeTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.root = self.d / "loyiha"
        self.outside = self.d / "tashqi"
        self.root.mkdir()
        self.outside.mkdir()
        (self.root / "ichki.md").write_text("MAXFIY ichki", encoding="utf-8")
        (self.d / "sir.md").write_text("MAXFIY tashqi", encoding="utf-8")
        (self.outside / "sir2.md").write_text("MAXFIY tashqi2", encoding="utf-8")
        self.tb = tools.Toolbox(tools.Context(root=str(self.root), web=False), "test")

    def test_dotdot_and_absolute_globs_rejected(self):
        for g in ("../*.md", "..\\*.md", "sub/../../*.md", str(self.d / "*.md"), "/etc/*", "C:/*"):
            with self.assertRaises(tools.ToolError, msg=g):
                self.tb.t_search_files("MAXFIY", glob=g)

    def test_normal_glob_still_works(self):
        out = self.tb.t_search_files("MAXFIY", glob="*.md")
        self.assertIn("ichki.md", out)
        self.assertNotIn("tashqi", out)

    def test_null_glob_means_all_files(self):
        out = self.tb.t_search_files("MAXFIY", glob=None)
        self.assertIn("ichki.md", out)
        self.assertNotIn("tashqi", out)

    def test_symlink_or_junction_outside_is_skipped(self):
        if not _link_dir(self.root / "havola", self.outside):
            self.skipTest("symlink/junction yaratib bo'lmadi")
        out = self.tb.t_search_files("MAXFIY")
        self.assertIn("ichki.md", out)
        self.assertNotIn("tashqi2", out)


class MemoryAndSkillsTests(unittest.TestCase):
    def test_memory_tools_hidden_and_refused_when_off(self):
        ctx = tools.Context(web=False, memory=False)
        names = {t.name for t in tools.available(ctx)}
        self.assertFalse(names & {"memory_search", "memory_remember", "memory_forget"})
        tb = tools.Toolbox(ctx, "test")
        with self.assertRaises(tools.ToolError):
            tb.t_memory_search("x")
        with self.assertRaises(tools.ToolError):
            tb.t_memory_remember("x")
        with self.assertRaises(tools.ToolError):
            tb.t_memory_forget("x")
        self.assertTrue(tb.run("memory_search", {"query": "x"})[1])
        self.assertNotIn("Local memory", tools.system_prompt(ctx))

    def test_memory_on_by_default(self):
        names = {t.name for t in tools.available(tools.Context(web=False))}
        self.assertIn("memory_search", names)

    def test_server_orchestrator_disables_memory_and_skills(self):
        d = Path(tempfile.mkdtemp())
        cfg = d / "agents.json"
        cfg.write_text(json.dumps({"web": False, "skills": True, "agents": [{"name": "aks", "type": "echo"}]}))
        with mock.patch.object(config, "user_dir", return_value=d):
            store = Store(":memory:")
            self.addCleanup(store.close)
            ctx = server.App(store, str(cfg)).orchestrator().ctx
        self.assertFalse(ctx.memory)
        self.assertFalse(ctx.skills)
        self.assertFalse({t.kind for t in tools.available(ctx)} & {"memory"})


class ForwardedForTests(unittest.TestCase):
    def handler(self, client_ip, headers):
        store = Store(":memory:")
        self.addCleanup(store.close)
        h = object.__new__(server.make_handler(server.App(store)))
        h.client_address, h.headers = (client_ip, 1234), headers
        return h

    def test_rightmost_value_used_from_local_proxy(self):
        h = self.handler("127.0.0.1", {"X-Forwarded-For": "1.1.1.1, 9.9.9.9"})
        self.assertEqual(h._ip(), "9.9.9.9")

    def test_not_trusted_from_remote_client(self):
        h = self.handler("10.0.0.5", {"X-Forwarded-For": "1.1.1.1"})
        self.assertEqual(h._ip(), "10.0.0.5")


class PostBodyLimitTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        cfg = self.d / "agents.json"
        cfg.write_text(json.dumps({"web": False, "agents": [{"name": "aks", "type": "echo"}]}))
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)
        self.store = Store(self.d / "server.db")
        self.httpd = server.create(self.store, config_file=str(cfg))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.store.close)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def post(self, path, length, body=b""):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        self.addCleanup(c.close)
        c.putrequest("POST", path)
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", str(length))
        c.endheaders(body)
        r = c.getresponse()
        r.read()  # o'qilmagan javob yopilishda RST ga olib keladi
        return r.status, r.getheader("Connection")

    def test_unauthenticated_big_body_rejected_without_reading(self):
        # tana yuborilmaydi: server uni kutmasdan 401 qaytarishi kerak
        self.assertEqual(self.post("/api/chat/new", server.MAX_BODY), (401, "close"))

    def test_unauthenticated_small_body_is_drained(self):
        self.assertEqual(self.post("/api/chat/new", 2, b"{}")[0], 401)

    def test_login_body_limit(self):
        self.assertEqual(self.post("/api/login", server.AUTH_BODY + 1), (413, "close"))


class CheckUrlTests(unittest.TestCase):
    def check(self, ip):
        info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
        with mock.patch.object(tools.socket, "getaddrinfo", return_value=info):
            tools._check_url("http://misol.uz/", False)

    def test_non_global_addresses_blocked(self):
        for ip in ("100.64.0.1", "100.127.255.254", "0.0.0.0", "127.0.0.1", "10.0.0.1", "169.254.1.1", "192.0.0.8"):
            with self.assertRaises(tools.ToolError, msg=ip):
                self.check(ip)

    def test_public_address_allowed(self):
        self.check("8.8.8.8")


if __name__ == "__main__":
    unittest.main()
