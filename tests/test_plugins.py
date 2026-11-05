import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from agent_umimiy import config, mcp, skills
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox

FAKE = str(Path(__file__).parent / "fixtures" / "fake_mcp.py")


def stdio_cfg(name="fake"):
    return {"name": name, "transport": "stdio", "command": f'"{sys.executable}" "{FAKE}"'}


class McpStdioTests(unittest.TestCase):
    def setUp(self):
        self.m = mcp.Manager([stdio_cfg()])
        self.addCleanup(self.m.shutdown)
        self.m.wait_ready(20)

    def test_tools_listed_with_clean_names_and_flags(self):
        self.assertEqual(self.m.servers["fake"].status, "tayyor", self.m.servers["fake"].error)
        tools = {t.remote_name: t for t in self.m.tools()}
        self.assertEqual(set(tools), {"echo", "save-note", "boom"})
        self.assertEqual(tools["save-note"].name, "fake__save-note")
        self.assertTrue(tools["echo"].read_only)
        self.assertFalse(tools["save-note"].read_only)
        self.assertNotIn("$schema", tools["echo"].parameters)

    def test_call_and_error(self):
        self.assertEqual(self.m.call("fake", "echo", {"text": "salom"}), "echo: salom")
        with self.assertRaises(mcp.McpError):
            self.m.call("fake", "boom", {})

    def test_bad_command_reports_error(self):
        m = mcp.Manager([{"name": "yoq", "transport": "stdio", "command": "bunday-dastur-yoq-xyz"}])
        self.addCleanup(m.shutdown)
        m.wait_ready(10)
        self.assertEqual(m.servers["yoq"].status, "xato")
        self.assertIn("topilmadi", m.servers["yoq"].error)
        self.assertEqual(m.tools(), [])

    def test_configure_diff(self):
        old = self.m.servers["fake"]
        self.m.configure([stdio_cfg(), stdio_cfg("ikkinchi")])
        self.assertIs(self.m.servers["fake"], old)  # o'zgarmagani qayta ishga tushmadi
        self.m.configure([{**stdio_cfg(), "enabled": False}])
        self.assertEqual(self.m.servers, {})


class McpToolboxTests(unittest.TestCase):
    def setUp(self):
        self.m = mcp.Manager([stdio_cfg()])
        self.addCleanup(self.m.shutdown)
        self.m.wait_ready(20)
        self.asked = []
        self.answer = "yes"
        self.ctx = Context(mcp=self.m, skills=False, confirm=lambda *a: (self.asked.append(a), self.answer)[1],
                           emit=lambda *a: None)
        self.tb = Toolbox(self.ctx, "t")

    def test_read_only_runs_without_asking_and_write_asks(self):
        out, err = self.tb.run("fake__echo", {"text": "x"})
        self.assertEqual((out, err), ("echo: x", False))
        self.assertEqual(self.asked, [])
        out, err = self.tb.run("fake__save-note", {"note": "n"})
        self.assertFalse(err)
        self.assertEqual(self.asked[0][1], "mcp:fake")
        self.assertIn('"note": "n"', self.asked[0][3])

    def test_denied_and_readonly_mode(self):
        self.answer = "no"
        self.assertTrue(self.tb.run("fake__save-note", {"note": "n"})[1])
        self.ctx.readonly = True
        names = [t.name for t in self.tb.tools()]
        self.assertIn("fake__echo", names)
        self.assertNotIn("fake__save-note", names)

    def test_tool_error_is_reported(self):
        out, err = self.tb.run("fake__boom", {})
        self.assertTrue(err)
        self.assertIn("buzildi", out)

    def test_agent_loop_uses_plugin_tool(self):
        from tests.test_tools import serve
        srv, seen = serve([
            {"content": [{"type": "tool_use", "id": "1", "name": "fake__echo", "input": {"text": "plagin"}}], "stop_reason": "tool_use"},
            {"content": [{"type": "text", "text": "tayyor"}], "stop_reason": "end_turn"}])
        a = build_agent({"name": "c", "type": "anthropic", "api_key": "k", "base_url": f"http://127.0.0.1:{srv.server_port}"})
        o = Orchestrator([a])
        o.ctx.mcp, o.ctx.skills = self.m, False
        r = o.run("echo ishlat", "single")[0]
        self.assertEqual(r.text, "tayyor")
        self.assertIn("fake__echo", [t["name"] for t in seen[0]["tools"]])
        self.assertEqual(seen[1]["messages"][-1]["content"][0]["content"], "echo: plagin")


def http_mcp(sse: bool, key="Bearer sir"):
    state = {"session": "S1"}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.headers.get("Authorization") != key:
                self.send_response(401)
                self.end_headers()
                return
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if "id" not in msg:
                self.send_response(202)
                self.end_headers()
                return
            m = msg["method"]
            res = ({"protocolVersion": "2024-11-05", "capabilities": {}} if m == "initialize" else
                   {"tools": [{"name": "salom", "description": "d", "inputSchema": {"type": "object"}}]} if m == "tools/list" else
                   {"content": [{"type": "text", "text": "sessiya:" + str(self.headers.get("Mcp-Session-Id"))}]})
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": res}
            if sse:
                out = ("event: message\ndata: " + json.dumps(body) + "\n\n").encode()
                ctype = "text/event-stream"
            else:
                out, ctype = json.dumps(body).encode(), "application/json"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Mcp-Session-Id", state["session"])
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class McpHttpTests(unittest.TestCase):
    def _run(self, sse):
        srv = http_mcp(sse)
        m = mcp.Manager([{"name": "uzoq", "transport": "http", "url": f"http://127.0.0.1:{srv.server_port}/mcp",
                          "headers": "Authorization: Bearer sir"}])
        self.addCleanup(m.shutdown)
        m.wait_ready(10)
        self.assertEqual(m.servers["uzoq"].status, "tayyor", m.servers["uzoq"].error)
        self.assertEqual(m.call("uzoq", "salom", {}), "sessiya:S1")  # sessiya sarlavhasi qaytarilgan

    def test_json_response(self):
        self._run(False)

    def test_sse_response(self):
        self._run(True)

    def test_wrong_key(self):
        srv = http_mcp(False)
        m = mcp.Manager([{"name": "uzoq", "transport": "http", "url": f"http://127.0.0.1:{srv.server_port}/", "headers": "Authorization: Bearer xato"}])
        self.addCleanup(m.shutdown)
        m.wait_ready(10)
        self.assertEqual(m.servers["uzoq"].status, "xato")
        self.assertIn("Ruxsat yo'q", m.servers["uzoq"].error)


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.proj = Path(tempfile.mkdtemp())
        for p in (mock.patch.object(config, "user_dir", return_value=self.home / "app"),
                  mock.patch.object(Path, "home", return_value=self.home)):
            p.start()
            self.addCleanup(p.stop)
        skills._cache.clear()

    def make(self, root, name, desc, body="Qadamlar: 1) bir 2) ikki", extra=None, meta_name=None):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {meta_name or name}\ndescription: {desc}\n---\n{body}\n")
        for f, t in (extra or {}).items():
            (d / f).parent.mkdir(parents=True, exist_ok=True)
            (d / f).write_text(t)

    def test_discovery_priority_and_sources(self):
        self.make(self.home / ".claude" / "skills", "hisobot", "Claude versiyasi")
        self.make(self.home / "app" / "skills", "hisobot", "Bizning versiya")
        self.make(self.proj / ".claude" / "skills", "loyiha-qoidasi", "Loyiha uchun")
        self.make(self.home / ".claude" / "plugins" / "p" / "skills", "plaginniki", "Plagindan")
        found = {s.name: s for s in skills.discover(str(self.proj), ttl=0)}
        self.assertEqual(set(found), {"hisobot", "loyiha-qoidasi", "plaginniki"})
        self.assertEqual(found["hisobot"].description, "Bizning versiya")  # o'zimizniki Claude'nikidan ustun
        self.assertEqual(found["plaginniki"].source, "Claude plagin")

    def test_folded_description_and_load(self):
        d = self.home / "app" / "skills" / "uzun"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: uzun\ndescription: >\n  birinchi qator\n  ikkinchi qator\n---\nASOSIY MATN")
        (d / "ref").mkdir()
        (d / "ref" / "qoida.md").write_text("QOIDA")
        sk = skills.discover(None, ttl=0)[0]
        self.assertEqual(sk.description, "birinchi qator ikkinchi qator")
        self.assertIn("ASOSIY MATN", skills.load("uzun"))
        self.assertIn("ref/qoida.md".replace("/", __import__("os").sep), skills.load("uzun"))
        self.assertEqual(skills.load("uzun", file="ref/qoida.md"), "QOIDA")
        with self.assertRaises(ValueError):
            skills.load("uzun", file="../../etc/passwd")
        with self.assertRaises(KeyError):
            skills.load("yoq")

    def test_toolbox_use_skill_and_prompt(self):
        self.make(self.home / "app" / "skills", "tarjima", "Tarjima qilish qoidalari", body="Faqat ravon tarjima qiling.")
        skills._cache.clear()
        ctx = Context()
        from agent_umimiy.tools import system_prompt
        sp = system_prompt(ctx, "a")
        self.assertIn("tarjima: Tarjima qilish qoidalari", sp)
        tb = Toolbox(ctx, "a")
        self.assertIn("use_skill", [t.name for t in tb.tools()])
        out, err = tb.run("use_skill", {"name": "tarjima"})
        self.assertEqual((out.strip(), err), ("Faqat ravon tarjima qiling.", False))
        self.assertTrue(tb.run("use_skill", {"name": "yoq"})[1])
        self.assertTrue(tb.run("use_skill", {"name": "tarjima", "file": "../x"})[1])
        ctx.skills = False
        self.assertNotIn("use_skill", [t.name for t in Toolbox(ctx, "a").tools()])


if __name__ == "__main__":
    unittest.main()
