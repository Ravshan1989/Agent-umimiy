import base64
import json
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from agent_umimiy import attachments as att
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox, _html_text, _parse_ddg
from tests.test_tools import serve

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def make_pdf(text: str) -> bytes:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>"]
    stream = f"BT /F1 18 Tf 10 50 Td ({text}) Tj ET"
    objs += [f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()


class AttachTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "a.png").write_bytes(PNG)
        (self.d / "d.pdf").write_bytes(make_pdf("Salom PDF dunyo"))
        (self.d / "n.txt").write_text("matn fayl")
        with zipfile.ZipFile(self.d / "w.docx", "w") as z:
            z.writestr("word/document.xml", "<w:p><w:t>Word matni</w:t></w:p>")

    def test_kinds_and_errors(self):
        self.assertEqual(att.load(str(self.d / "a.png")).kind, "image")
        self.assertEqual(att.load(str(self.d / "d.pdf")).kind, "pdf")
        self.assertIn("Word matni", att.load(str(self.d / "w.docx")).text)
        (self.d / "b.bin").write_bytes(b"\x00\x01\x02")
        with self.assertRaises(att.AttachError):
            att.load(str(self.d / "b.bin"))
        with self.assertRaises(att.AttachError):
            att.load(str(self.d / "yoq.png"))

    def test_pdf_text(self):
        self.assertIn("Salom PDF", att.pdf_text(att.load(str(self.d / "d.pdf")).data))

    def _run(self, kind, files, script):
        srv, seen = serve(script)
        opts = {"anthropic": {"base_url": f"http://127.0.0.1:{srv.server_port}"},
                "openai": {"base_url": f"http://127.0.0.1:{srv.server_port}"}}[kind]
        a = build_agent({"name": "x", "type": kind, "api_key": "k", "tools": False, **opts})
        r = Orchestrator([a]).run("Bu nima?", "single", files=[att.load(str(self.d / f)) for f in files])[0]
        return r, seen[0]

    def test_anthropic_image_and_pdf_blocks(self):
        r, body = self._run("anthropic", ["a.png", "d.pdf", "n.txt"], [{"content": [{"type": "text", "text": "ok"}]}])
        self.assertTrue(r.ok, r.error)
        blocks = body["messages"][-1]["content"]
        self.assertEqual([b["type"] for b in blocks], ["image", "document", "text"])
        self.assertEqual(blocks[0]["source"]["media_type"], "image/png")
        self.assertIn("matn fayl", blocks[-1]["text"])

    def test_openai_image_and_pdf_as_text(self):
        r, body = self._run("openai", ["a.png", "d.pdf"], [{"choices": [{"message": {"content": "ok"}}]}])
        self.assertTrue(r.ok, r.error)
        parts = body["messages"][-1]["content"]
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertIn("Salom PDF", parts[0]["text"])

    def test_history_keeps_only_note(self):
        o = Orchestrator([build_agent({"name": "e", "type": "echo"})])
        o.run("savol", "single", files=[att.load(str(self.d / "a.png"))])
        self.assertEqual(o.history[0]["content"], "savol\n[Biriktirilgan: a.png]")


def page_server(pages):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redir":
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest")
                self.end_headers()
                return
            body = pages.get(self.path, "yo'q").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class WebTests(unittest.TestCase):
    def test_fetch_extracts_text_and_blocks_private(self):
        srv = page_server({"/": "<html><head><title>x</title><style>a{}</style></head><body><h1>Salom</h1>"
                                "<script>evil()</script><p>Dunyo &amp; olam</p></body></html>"})
        url = f"http://127.0.0.1:{srv.server_port}/"
        tb = Toolbox(Context(allow_private=True), "t")
        out, err = tb.run("web_fetch", {"url": url})
        self.assertFalse(err)
        self.assertIn("Dunyo & olam", out)
        self.assertNotIn("evil", out)
        tb2 = Toolbox(Context(), "t")  # standart: ichki manzillar yopiq
        self.assertTrue(tb2.run("web_fetch", {"url": url})[1])
        self.assertTrue(tb2.run("web_fetch", {"url": "file:///etc/passwd"})[1])
        self.assertTrue(tb2.run("web_fetch", {"url": "http://localhost:1/"})[1])

    def test_redirect_to_private_blocked(self):
        srv = page_server({})
        tb = Toolbox(Context(allow_private=False), "t")
        # 127.0.0.1 ning o'zi yopiq; redirect tekshiruvini alohida tekshiramiz
        from agent_umimiy.tools import ToolError, _check_url
        with self.assertRaises(ToolError):
            _check_url("http://169.254.169.254/latest", False)
        with self.assertRaises(ToolError):
            _check_url("http://10.0.0.5/", False)

    def test_parse_ddg(self):
        html_ = ('<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&amp;rut=1">'
                 'Misol <b>sarlavha</b></a><a class="result__snippet" href="x">Qisqa <b>tavsif</b></a>')
        out = _parse_ddg(html_)
        self.assertIn("https://example.com/a", out)
        self.assertIn("Misol sarlavha", out)
        self.assertIn("Qisqa tavsif", out)

    def test_tool_lists(self):
        names = lambda ctx: {t.name for t in Toolbox(ctx, "t").tools()}
        self.assertEqual(names(Context()), {"web_search", "web_fetch", "open_url", "todo_write"})
        self.assertIn("write_file", names(Context(root=tempfile.mkdtemp())))
        self.assertNotIn("web_fetch", names(Context(root=tempfile.mkdtemp(), web=False)))
        tb = Toolbox(Context(), "t")  # loyihasiz fayl asbobi yo'q
        self.assertTrue(tb.run("read_file", {"path": "x"})[1])

    def test_search_via_agent_loop(self):
        srv = page_server({"/": "<p>Javob sahifasi</p>"})
        call = {"id": "1", "type": "function", "function": {"name": "web_fetch",
                "arguments": json.dumps({"url": f"http://127.0.0.1:{srv.server_port}/"})}}
        api, seen = serve([{"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call]}}]},
                           {"choices": [{"message": {"role": "assistant", "content": "Topdim"}}]}])
        a = build_agent({"name": "g", "type": "openai", "api_key": "k", "base_url": f"http://127.0.0.1:{api.server_port}"})
        o = Orchestrator([a])
        o.ctx.allow_private = True
        r = o.run("internetdan top", "single")[0]
        self.assertEqual(r.text, "Topdim")
        self.assertIn("Javob sahifasi", seen[1]["messages"][-1]["content"])
        self.assertIn("web_fetch", [t["function"]["name"] for t in seen[0]["tools"]])
        self.assertNotIn("write_file", [t["function"]["name"] for t in seen[0]["tools"]])  # loyiha yo'q


if __name__ == "__main__":
    unittest.main()
