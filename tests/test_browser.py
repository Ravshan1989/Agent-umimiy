import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent_umimiy import browser as br
from agent_umimiy.tools import Context, Toolbox

PAGES = {
    "/": """<html><head><title>Sinov sahifa</title></head><body>
      <h1>Salom brauzer</h1>
      <input id="n" name="ism" placeholder="Ismingiz">
      <input id="p" type="password" placeholder="Parol">
      <button id="b" onclick="document.getElementById('out').textContent='Salom, ' + document.getElementById('n').value + '!'">Yuborish</button>
      <div id="out">hali yo'q</div>
      <a href="/ikkinchi">Ikkinchi sahifa</a>
      <div style="display:none"><button>Yashirin</button></div>
    </body></html>""",
    "/ikkinchi": "<html><head><title>Ikkinchi</title></head><body><p>Bu ikkinchi sahifa matni</p><a href='/'>Bosh sahifa</a></body></html>",
}


def serve():
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = PAGES.get(self.path, "yo'q").encode()
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


class WebSocketFrameTests(unittest.TestCase):
    def test_find_browser_env_override(self):
        import os
        import sys
        old = os.environ.get("AGENT_BROWSER")
        os.environ["AGENT_BROWSER"] = sys.executable
        try:
            self.assertEqual(br.find_browser(), sys.executable)
        finally:
            os.environ.pop("AGENT_BROWSER", None) if old is None else os.environ.__setitem__("AGENT_BROWSER", old)

    def test_format_snapshot(self):
        s = br.format_snapshot({"url": "http://a", "title": "T", "text": "matn", "elements": [
            {"i": 1, "tag": "input", "type": "text", "label": "Ism", "name": "", "href": "", "checked": None},
            {"i": 2, "tag": "a", "type": "", "label": "Havola", "name": "", "href": "/x", "checked": None}]})
        self.assertIn("1. <input type=text> Ism", s)
        self.assertIn("2. <a> Havola -> /x", s)
        self.assertIn("ishonchsiz", s)


@unittest.skipUnless(br.find_browser(), "Chrome/Edge topilmadi")
class RealBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = serve()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}/"
        cls.b = br.Browser(profile_dir=tempfile.mkdtemp(), headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.b.close()

    def test_1_open_read_type_click(self):
        out = self.b.open(self.url)
        self.assertIn("Salom brauzer", out)
        self.assertIn("Sinov sahifa", out)
        self.assertNotIn("Yashirin", out)  # ko'rinmas elementlar yo'q
        ids = {line.split(".")[0]: line for line in out.splitlines() if line[:1].isdigit()}
        inp = next(k for k, v in ids.items() if "Ismingiz" in v)
        btn = next(k for k, v in ids.items() if "Yuborish" in v)
        self.b.type(int(inp), "Ravshan")
        out = self.b.click(int(btn))
        self.assertIn("Salom, Ravshan!", out)

    def test_2_password_blocked(self):
        out = self.b.open(self.url)
        pw = next(line.split(".")[0] for line in out.splitlines() if "type=password" in line)
        with self.assertRaises(br.BrowserError) as cm:
            self.b.type(int(pw), "maxfiy")
        self.assertIn("Parol", str(cm.exception))

    def test_3_navigate_back_scroll_press(self):
        out = self.b.open(self.url)
        link = next(line.split(".")[0] for line in out.splitlines() if "Ikkinchi sahifa" in line and line[:1].isdigit())
        out = self.b.click(int(link))
        self.assertIn("Bu ikkinchi sahifa matni", out)
        self.assertIn("Salom brauzer", self.b.back())
        self.assertIn("URL:", self.b.scroll("down"))
        self.assertIn("URL:", self.b.press("Tab"))
        with self.assertRaises(br.BrowserError):
            self.b.press("F13")

    def test_4_stale_element(self):
        self.b.open(self.url)
        with self.assertRaises(br.BrowserError) as cm:
            self.b.click(999)
        self.assertIn("topilmadi", str(cm.exception))


@unittest.skipUnless(br.find_browser(), "Chrome/Edge topilmadi")
class BrowserToolTests(unittest.TestCase):
    def setUp(self):
        self.srv = serve()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/"
        self.asked = []
        self.answer = "yes"
        br._shared = br.Browser(profile_dir=tempfile.mkdtemp(), headless=True)
        self.addCleanup(br.shutdown)
        self.ctx = Context(confirm=lambda *a: (self.asked.append(a), self.answer)[1], emit=lambda *a: None)
        self.tb = Toolbox(self.ctx, "t")

    def test_site_permission_asked_once_and_typing_asks_each_time(self):
        out, err = self.tb.run("browser_open", {"url": self.url})
        self.assertFalse(err, out)
        self.assertEqual(self.asked[0][1], "browser:127.0.0.1")
        self.tb.run("browser_open", {"url": self.url})
        self.assertEqual(len(self.asked), 1)  # shu sayt uchun qayta so'ralmaydi
        n = next(l.split(".")[0] for l in out.splitlines() if "Ismingiz" in l)
        self.tb.run("browser_type", {"id": int(n), "text": "a"})
        self.tb.run("browser_type", {"id": int(n), "text": "b"})
        self.assertEqual([a[1] for a in self.asked].count("browser_type"), 2)

    def test_denied_does_not_start_browser(self):
        self.answer = "no"
        out, err = self.tb.run("browser_open", {"url": self.url})
        self.assertTrue(err)
        self.assertIsNone(br._shared.proc)

    def test_bad_schemes_and_readonly(self):
        for u in ("file:///etc/passwd", "javascript:alert(1)", "chrome://settings"):
            self.assertTrue(self.tb.run("browser_open", {"url": u})[1], u)
        self.assertEqual(self.asked, [])
        self.ctx.readonly = True
        self.assertNotIn("browser_open", [t.name for t in self.tb.tools()])
        self.assertTrue(self.tb.run("browser_open", {"url": self.url})[1])
        self.ctx.readonly, self.ctx.browser = False, False
        self.assertNotIn("browser_click", [t.name for t in self.tb.tools()])


if __name__ == "__main__":
    unittest.main()
