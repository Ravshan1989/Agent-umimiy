import json
import unittest
import urllib.error
import urllib.request

from agent_umimiy import remote
from agent_umimiy.remote_page import PAGE


def req(srv, path, token="sir", body=None, raw=None):
    url = f"http://127.0.0.1:{srv.port}{path}"
    h = {"X-Token": token} if token is not None else {}
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


class RemoteServerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def handler(action, payload):
            self.calls.append((action, payload))
            if action == "boom":
                raise ValueError("xato bo'ldi")
            return {"ok": True, "action": action}

        self.srv = remote.RemoteServer(handler, "sir", port=0, host="127.0.0.1")
        self.srv.start()
        self.addCleanup(self.srv.stop)

    def test_page_is_public_but_has_security_headers(self):
        code, h, body = req(self.srv, "/", token=None)
        self.assertEqual(code, 200)
        self.assertIn(b"Agent Umimiy", body)
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["Cache-Control"], "no-store")
        self.assertNotIn("sir", PAGE)  # sahifada hech qanday kalit yo'q

    def test_api_requires_token(self):
        for tok in (None, "", "xato", "sir "):
            self.assertEqual(req(self.srv, "/api/state", token=tok)[0], 401, tok)
            self.assertEqual(req(self.srv, "/api/send", token=tok, body={"text": "x"})[0], 401)
        self.assertEqual(self.calls, [])  # tokensiz hech narsa bajarilmadi
        self.assertEqual(req(self.srv, "/api/state?chat=&since=0")[0], 200)

    def test_token_in_url_query_is_not_accepted_for_api(self):
        self.assertEqual(req(self.srv, "/api/state?t=sir", token=None)[0], 401)

    def test_brute_force_lockout(self):
        for _ in range(20):
            self.srv.fail("127.0.0.1")
        code, _, body = req(self.srv, "/api/state", token="sir")  # to'g'ri token ham bloklangan
        self.assertEqual(code, 429)
        self.assertIn("noto'g'ri urinish", json.loads(body)["error"])

    def test_bad_requests(self):
        self.assertEqual(req(self.srv, "/api/send", raw=b"{buzuq")[0], 400)
        self.assertEqual(req(self.srv, "/api/send", raw=b"[1,2]")[0], 400)
        self.assertEqual(req(self.srv, "/api/yoq", body={})[0], 404)
        self.assertEqual(req(self.srv, "/api/state?chat=abc")[0], 400)
        self.assertEqual(req(self.srv, "/yoq")[0], 404)

    def test_handler_errors_become_json(self):
        self.srv.handler = lambda a, p: (_ for _ in ()).throw(ValueError("Agent band"))
        code, _, body = req(self.srv, "/api/send", body={"chat": 1, "text": "x"})
        self.assertEqual((code, json.loads(body)["error"]), (400, "Agent band"))

    def test_oversize_body_rejected(self):
        r = urllib.request.Request(f"http://127.0.0.1:{self.srv.port}/api/send", data=b"{}", method="POST",
                                   headers={"X-Token": "sir", "Content-Length": str(remote.MAX_BODY + 1)})
        with self.assertRaises((urllib.error.HTTPError, urllib.error.URLError, ConnectionError)):
            urllib.request.urlopen(r, timeout=5)

    def test_actions_routed(self):
        for path, action in remote.ACTIONS.items():
            code, _, body = req(self.srv, path, body={"x": 1})
            self.assertEqual((code, json.loads(body)["action"]), (200, action))

    def test_url_and_token(self):
        self.assertTrue(self.srv.url("192.168.0.5").startswith("http://192.168.0.5:"))
        self.assertTrue(self.srv.url("1.2.3.4").endswith("?t=sir"))
        a, b = remote.new_token(), remote.new_token()
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(len(a), 30)


class PageSafetyTests(unittest.TestCase):
    def test_no_external_resources_and_escaping(self):
        self.assertNotIn("http://", PAGE.replace("https?:", ""))
        self.assertNotIn("<script src", PAGE)
        self.assertIn("function esc(", PAGE)
        self.assertIn("rel=\"noopener noreferrer\"", PAGE)


if __name__ == "__main__":
    unittest.main()
