import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from agent_umimiy import gitutil
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox


def serve(script):
    """Soxta API: har so'rovga ketma-ket 'script' dagi javobni beradi."""
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            out = json.dumps(script[min(len(seen) - 1, len(script) - 1)]).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


class ToolboxTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = Path(self.d)
        self.asked = []
        self.events = []
        self.answer = "yes"
        self.ctx = Context(root=self.d, confirm=lambda *a: (self.asked.append(a), self.answer)[1],
                           emit=lambda *a: self.events.append(a))
        self.tb = Toolbox(self.ctx, "t")

    def test_write_read_edit(self):
        out, err = self.tb.run("write_file", {"path": "a/x.txt", "content": "salom\ndunyo\n"})
        self.assertFalse(err)
        self.assertEqual((self.root / "a/x.txt").read_text(), "salom\ndunyo\n")
        out, _ = self.tb.run("read_file", {"path": "a/x.txt"})
        self.assertIn("dunyo", out)
        out, err = self.tb.run("edit_file", {"path": "a/x.txt", "old_string": "dunyo", "new_string": "olam"})
        self.assertFalse(err)
        self.assertEqual((self.root / "a/x.txt").read_text(), "salom\nolam\n")
        self.assertIn("olam", self.asked[-1][3])  # ruxsat oynasida diff ko'rsatiladi

    def test_edit_ambiguous_and_missing(self):
        (self.root / "f.txt").write_text("a a")
        self.assertTrue(self.tb.run("edit_file", {"path": "f.txt", "old_string": "a", "new_string": "b"})[1])
        self.assertTrue(self.tb.run("edit_file", {"path": "f.txt", "old_string": "zzz", "new_string": "b"})[1])
        self.assertFalse(self.tb.run("edit_file", {"path": "f.txt", "old_string": "a", "new_string": "b",
                                                   "replace_all": True})[1])
        self.assertEqual((self.root / "f.txt").read_text(), "b b")

    def test_crlf_preserved(self):
        (self.root / "w.txt").write_bytes(b"one\r\ntwo\r\n")
        self.tb.run("edit_file", {"path": "w.txt", "old_string": "one\ntwo", "new_string": "1\n2"})
        self.assertEqual((self.root / "w.txt").read_bytes(), b"1\r\n2\r\n")

    def test_path_escape_blocked(self):
        for p in ("../etc/passwd", "/etc/passwd", "a/../../x"):
            out, err = self.tb.run("read_file", {"path": p})
            self.assertTrue(err, p)
        self.assertTrue(self.tb.run("write_file", {"path": ".git/config", "content": "x"})[1])

    def test_denied_and_readonly(self):
        self.answer = "no"
        out, err = self.tb.run("write_file", {"path": "n.txt", "content": "x"})
        self.assertTrue(err)
        self.assertFalse((self.root / "n.txt").exists())
        self.ctx.readonly = True
        self.assertTrue(self.tb.run("run_command", {"command": "echo hi"})[1])
        self.assertEqual(len(self.asked), 1)  # readonly rejimda so'ralmaydi ham

    def test_always_allows_without_asking_again(self):
        self.answer = "always"
        self.tb.run("write_file", {"path": "1.txt", "content": "1"})
        self.tb.run("write_file", {"path": "2.txt", "content": "2"})
        self.assertEqual(len(self.asked), 1)

    def test_search_list_run(self):
        (self.root / "m.py").write_text("def foo():\n    return 1\n")
        self.assertIn("m.py:1", self.tb.run("search_files", {"pattern": r"def \w+"})[0])
        self.assertIn("m.py", self.tb.run("list_dir", {})[0])
        out, err = self.tb.run("run_command", {"command": "echo salom"})
        self.assertIn("salom", out)
        self.assertIn("exit code: 0", out)

    def test_run_command_asks(self):
        self.answer = "no"
        self.assertTrue(self.tb.run("run_command", {"command": "echo x"})[1])
        self.assertEqual(self.asked[0][1], "run")


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _orch(self, agent):
        o = Orchestrator([agent])
        o.ctx.root = self.d
        o.ctx.confirm = lambda *a: "yes"
        return o

    def test_anthropic_loop_writes_file(self):
        srv, seen = serve([
            {"content": [{"type": "text", "text": "yozaman"},
                         {"type": "tool_use", "id": "t1", "name": "write_file",
                          "input": {"path": "hello.py", "content": "print('hi')\n"}}], "stop_reason": "tool_use"},
            {"content": [{"type": "text", "text": "Tayyor!"}], "stop_reason": "end_turn"},
        ])
        a = build_agent({"name": "c", "type": "anthropic", "api_key": "k",
                         "base_url": f"http://127.0.0.1:{srv.server_port}"})
        r = self._orch(a).run("hello.py yarat", "single")[0]
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.text, "Tayyor!")
        self.assertEqual((Path(self.d) / "hello.py").read_text(), "print('hi')\n")
        self.assertEqual(seen[1]["messages"][-1]["content"][0]["type"], "tool_result")
        self.assertIn(self.d, seen[0]["system"])

    def test_openai_loop_runs_command(self):
        call = {"id": "c1", "type": "function", "function": {"name": "run_command", "arguments": '{"command": "echo ok123"}'}}
        srv, seen = serve([
            {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]}}]},
            {"choices": [{"message": {"role": "assistant", "content": "Bajarildi"}}]},
        ])
        a = build_agent({"name": "g", "type": "openai", "api_key": "k", "base_url": f"http://127.0.0.1:{srv.server_port}"})
        r = self._orch(a).run("echo qil", "single")[0]
        self.assertEqual(r.text, "Bajarildi")
        self.assertIn("ok123", seen[1]["messages"][-1]["content"])

    def test_broadcast_is_readonly(self):
        srv, seen = serve([
            {"content": [{"type": "tool_use", "id": "t1", "name": "write_file",
                          "input": {"path": "x.txt", "content": "x"}}], "stop_reason": "tool_use"},
            {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"},
        ])
        a = build_agent({"name": "c", "type": "anthropic", "api_key": "k", "base_url": f"http://127.0.0.1:{srv.server_port}"})
        self._orch(a).run("yoz", "broadcast")
        self.assertFalse((Path(self.d) / "x.txt").exists())
        self.assertTrue(seen[1]["messages"][-1]["content"][0]["is_error"])

    def test_cli_agent_uses_project_as_cwd(self):
        import sys
        a = build_agent({"name": "cli", "type": "cli",
                         "command": f"{sys.executable} -c \"import os;print(os.getcwd())\""})
        r = self._orch(a).run("x", "single")[0]
        self.assertEqual(Path(r.text).resolve(), Path(self.d).resolve())


class CliResolveTests(unittest.TestCase):
    def test_missing_program_message(self):
        r = build_agent({"name": "c", "type": "cli", "command": "yoq-dastur-xyz -p {prompt}"}).ask("x")
        self.assertFalse(r.ok)
        self.assertIn("topilmadi", r.error)
        self.assertIn("yoq-dastur-xyz", r.error)

    def test_cmd_shim_gets_prompt_via_stdin(self):
        import os
        import stat
        d = Path(tempfile.mkdtemp())
        shim = d / "fakeclaude.cmd"  # Windows'dagi npm shimini taqlid qiladi
        shim.write_text("#!/bin/sh\necho \"ARGS:$#\"\ncat\n")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
        old = os.environ["PATH"]
        os.environ["PATH"] = f"{d}{os.pathsep}{old}"
        try:
            prompt = 'a & b | "c" > d %PATH% ^'
            r = build_agent({"name": "c", "type": "cli", "command": "fakeclaude.cmd -p {prompt}"}).ask(prompt)
        finally:
            os.environ["PATH"] = old
        self.assertTrue(r.ok, r.error)
        self.assertTrue(r.text.startswith("ARGS:1"), r.text)  # faqat -p, so'rov argumentda emas
        self.assertIn(prompt, r.text)


@unittest.skipUnless(gitutil.have_git(), "git yo'q")
class GitTests(unittest.TestCase):
    def test_flow(self):
        d = tempfile.mkdtemp()
        self.assertFalse(gitutil.is_repo(d))
        gitutil.run(d, "init")
        gitutil.run(d, "config", "user.email", "t@t")
        gitutil.run(d, "config", "user.name", "T")
        (Path(d) / "a.txt").write_text("1")
        self.assertEqual(gitutil.status(d)[0][1], "a.txt")
        ok, out = gitutil.commit_all(d, "birinchi")
        self.assertTrue(ok, out)
        self.assertEqual(gitutil.status(d), [])
        (Path(d) / "a.txt").write_text("2")
        self.assertEqual(gitutil.status(d)[0][0], "o'zgargan")
        self.assertIn("+2", gitutil.diff(d))


if __name__ == "__main__":
    unittest.main()
