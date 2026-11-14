import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from agent_umimiy import gitutil
from agent_umimiy import tools as tools_mod
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox, project_notes


def _sse(events) -> bytes:
    return "".join(f"data: {json.dumps(e)}\n\n" for e in events).encode()


def as_stream(resp: dict) -> bytes:
    """Tayyor javobni provayder oqimiga aylantiradi: matn ikki bo'lakda, asbob argumentlari ham bo'laklab keladi."""
    def halves(x):
        return [x[:len(x) // 2], x[len(x) // 2:]]

    if "content" in resp:  # Anthropic
        ev = [{"type": "message_start", "message": {"role": "assistant", "content": []}}]
        for i, b in enumerate(resp["content"]):
            if b["type"] == "text":
                ev.append({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
                ev += [{"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": h}} for h in halves(b["text"])]
            else:
                ev.append({"type": "content_block_start", "index": i, "content_block": {**b, "input": {}}})
                ev += [{"type": "content_block_delta", "index": i, "delta": {"type": "input_json_delta", "partial_json": h}}
                       for h in halves(json.dumps(b["input"]))]
            ev.append({"type": "content_block_stop", "index": i})
        return _sse(ev + [{"type": "message_stop"}])
    msg = resp["choices"][0]["message"]  # OpenAI-mos
    ev = [{"choices": [{"delta": {"role": "assistant", "content": h}}]} for h in halves(msg.get("content") or "")]
    for i, c in enumerate(msg.get("tool_calls") or []):
        ev.append({"choices": [{"delta": {"tool_calls": [{"index": i, "id": c["id"], "type": "function",
                                                         "function": {"name": c["function"]["name"], "arguments": ""}}]}}]})
        ev += [{"choices": [{"delta": {"tool_calls": [{"index": i, "function": {"arguments": h}}]}}]}
               for h in halves(c["function"]["arguments"])]
    return _sse(ev) + b"data: [DONE]\n\n"


def serve(script):
    """Soxta API: har so'rovga ketma-ket 'script' dagi javobni oqim (streaming) ko'rinishida beradi."""
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            out = as_stream(script[min(len(seen) - 1, len(script) - 1)])
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


class ProjectNotesTests(unittest.TestCase):
    def test_instruction_symlink_is_rejected_and_content_is_bounded(self):
        root = Path(tempfile.mkdtemp())
        outside = root.parent / (root.name + "-outside.md")
        outside.write_text("SECRET")
        link = root / "CLAUDE.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink yaratish huquqi yo'q")
        self.assertEqual(project_notes(str(root)), "")
        link.unlink()
        link.write_text("x" * 30_000)
        self.assertLessEqual(len(project_notes(str(root))), 20_200)


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

    def test_always_approval_is_scoped_to_one_file(self):
        self.answer = "always"
        self.tb.run("write_file", {"path": "1.txt", "content": "1"})
        self.tb.run("write_file", {"path": "2.txt", "content": "2"})
        self.tb.run("write_file", {"path": "1.txt", "content": "updated"})
        self.assertEqual(len(self.asked), 2)

    def test_create_document_requires_approval(self):
        folder = self.root / "out"
        self.ctx.files_dir = str(folder)
        self.answer = "no"
        self.assertTrue(self.tb.run("create_document", {"name": "report.txt", "content": "hello"})[1])
        self.assertFalse((folder / "report.txt").exists())
        self.assertEqual(self.asked[-1][1], "create:report.txt")
        self.answer = "yes"
        out, err = self.tb.run("create_document", {"name": "report.txt", "content": "hello"})
        self.assertFalse(err, out)
        self.assertTrue((folder / "report.txt").is_file())

    def test_always_run_permission_is_scoped_to_exact_command(self):
        self.answer = "always"
        self.tb.run("run_command", {"command": "echo same"})
        self.tb.run("run_command", {"command": "echo same"})
        self.tb.run("run_command", {"command": "echo different"})
        self.assertEqual(len(self.asked), 2)

    def test_search_list_run(self):
        (self.root / "m.py").write_text("def foo():\n    return 1\n")
        self.assertIn("m.py:1", self.tb.run("search_files", {"pattern": r"def \w+"})[0])
        self.assertIn("m.py", self.tb.run("list_dir", {})[0])
        out, err = self.tb.run("run_command", {"command": "echo salom"})
        self.assertIn("salom", out)
        self.assertIn("exit code: 0", out)

    def test_timed_out_command_keeps_its_output_and_warns_about_partial_work(self):
        slow = (f"{sys.executable} -c \"import sys,time; print('boshlandi', flush=True); time.sleep(30)\"")
        started = time.monotonic()
        out, err = self.tb.run("run_command", {"command": slow, "timeout": 2})
        # Chegaradan keyin buyruq bolalari bilan o'ldiriladi: aks holda shell=True bilan nabira jarayon
        # ishlashda davom etadi va chaqiruv 30 soniya osilib qoladi.
        self.assertLess(time.monotonic() - started, 20, "buyruq chegaradan keyin ham ishlashda davom etdi")
        self.assertTrue(err, out)
        self.assertIn("qisman", out)  # agent ishni bajarilgan deb o'ylamasin
        self.assertIn("900", out)  # kattaroq chegara bilan qayta urinish mumkinligi aytiladi
        self.assertIn("boshlandi", out)  # to'xtatilgunga qadar olingan chiqish yo'qolmaydi

    def test_slow_command_finishes_when_the_timeout_is_large_enough(self):
        quick = f"{sys.executable} -c \"import time; time.sleep(1); print('tugadi')\""
        out, err = self.tb.run("run_command", {"command": quick, "timeout": 60})
        self.assertFalse(err, out)
        self.assertIn("tugadi", out)

    def test_check_program_reports_the_truth_and_refuses_other_names(self):
        """Agent dasturni tekshira olsin, lekin bu orqali o'zboshimcha buyruq ishga tushira olmasin."""
        out, err = self.tb.run("check_program", {"name": "python"})
        self.assertFalse(err, out)
        self.assertIn("o'rnatilgan", out)
        out, err = self.tb.run("check_program", {"name": "bunday-dastur-yo'q; echo salom"})
        self.assertTrue(err)
        self.assertIn("Faqat shu dasturlarni", out)
        with mock.patch.object(tools_mod.shutil, "which", return_value=None):
            out, err = self.tb.run("check_program", {"name": "ffmpeg"})
        self.assertFalse(err, out)
        self.assertIn("o'rnatilmagan", out)

    def test_run_command_asks(self):
        self.answer = "no"
        self.assertTrue(self.tb.run("run_command", {"command": "echo x"})[1])
        self.assertTrue(self.asked[0][1].startswith("run:"))


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
        shim = d / "fakeclaude.cmd"  # Windows'dagi npm shimini taqlid qiladi: argumentlar sonini va stdin'ni chiqaradi
        if sys.platform == "win32":
            shim.write_text('@echo off\nset n=0\nfor %%a in (%*) do set /a n+=1\necho ARGS:%n%\nfindstr "^"\n')
        else:
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


class CliHealthTests(unittest.TestCase):
    """npm claude.cmd -> bin\\claude.exe: o'rnatish buzilgan bo'lsa, Windows 16-bit xatosi o'rniga tushunarli xabar."""

    def _npm(self, exe_bytes):
        d = Path(tempfile.mkdtemp())
        bindir = d / "node_modules" / "@anthropic-ai" / "claude-code" / "bin"
        bindir.mkdir(parents=True)
        (bindir / "claude.exe").write_bytes(exe_bytes)
        (d / "claude.cmd").write_text(
            '@ECHO off\r\nSETLOCAL\r\nSET dp0=%~dp0\r\n"%dp0%\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe"   %*\r\n')
        return d

    def test_stub_exe_is_detected(self):
        from agent_umimiy.detect import cli_health
        d = self._npm(b"#!/usr/bin/env node\nconsole.log('stub')\n")
        ok, msg = cli_health(str(d / "claude.cmd"))
        self.assertFalse(ok)
        self.assertIn("buzilgan", msg)
        self.assertIn("npm install -g @anthropic-ai/claude-code", msg)
        self.assertIn("claude.exe", msg)

    def test_real_exe_and_unknown_cases_pass(self):
        from agent_umimiy.detect import cli_health
        d = self._npm(b"MZ" + b"\x00" * 100)
        self.assertEqual(cli_health(str(d / "claude.cmd")), (True, ""))
        self.assertEqual(cli_health(str(d / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe")), (True, ""))
        self.assertEqual(cli_health("/bin/ls"), (True, ""))                 # PE bo'lmagan oddiy dastur
        self.assertEqual(cli_health(str(d / "yoq.cmd")), (True, ""))        # o'qib bo'lmasa — to'sqinlik qilmaymiz

    def test_agent_reports_instead_of_running(self):
        import os
        d = self._npm(b"stub matn")
        (d / "claude.cmd").rename(d / "fakeagent.cmd")  # mashinada haqiqiy `claude` bo'lishi mumkin
        (d / "fakeagent.cmd").chmod(0o755)  # Linux'da which() faqat bajariladigan fayllarni topadi
        old = os.environ["PATH"]
        os.environ["PATH"] = f"{d}{os.pathsep}{old}"
        try:
            r = build_agent({"name": "claude", "type": "cli", "command": "fakeagent.cmd -p {prompt}"}).ask("salom")
        finally:
            os.environ["PATH"] = old
        self.assertFalse(r.ok)
        self.assertIn("o'rnatilishi buzilgan", r.error)
