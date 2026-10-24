import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent_umimiy import detect
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context


def gateway(need_key=True, chat_status=200):
    seen = []

    class H(BaseHTTPRequestHandler):
        def _auth(self):
            if need_key and self.headers.get("Authorization") != "Bearer freellmapi-test":
                self.send_response(401)
                self.end_headers()
                return False
            return True

        def do_GET(self):
            if not self._auth():
                return
            out = json.dumps({"data": [{"id": "llama-free"}, {"id": "qwen-free"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            if not self._auth():
                return
            if "tools" in body and chat_status != 200:  # model asbobni tushunmaydi
                out = b'{"error":"tools unsupported"}'
                self.send_response(chat_status)
            else:
                out = json.dumps({"choices": [{"message": {"role": "assistant", "content": "Salom shlyuzdan"}}]}).encode()
                self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


class GatewayTests(unittest.TestCase):
    def test_list_models_with_key(self):
        srv, _ = gateway()
        base = f"http://127.0.0.1:{srv.server_port}/v1"
        self.assertEqual(detect.list_models(base, "freellmapi-test"), ["llama-free", "qwen-free"])
        with self.assertRaises(Exception):
            detect.list_models(base, "xato-kalit")

    def test_detect_gateway_asks_for_key(self):
        srv, _ = gateway()
        found = detect.freellmapi(f"http://127.0.0.1:{srv.server_port}")
        self.assertEqual(found[0]["type"], "openai")
        self.assertTrue(found[0]["base_url"].endswith("/v1"))
        self.assertNotIn("api_key", found[0])  # kalit hech qachon o'zimizdan yozilmaydi

    def test_detect_gateway_open(self):
        srv, _ = gateway(need_key=False)
        self.assertEqual(detect.freellmapi(f"http://127.0.0.1:{srv.server_port}")[0]["model"], "llama-free")

    def test_detect_nothing_running(self):
        self.assertEqual(detect.freellmapi("http://127.0.0.1:1"), [])

    def _chat(self, **kw):
        srv, seen = gateway(**kw)
        a = build_agent({"name": "f", "type": "openai", "api_key": "freellmapi-test", "model": "llama-free",
                         "base_url": f"http://127.0.0.1:{srv.server_port}/v1"})
        return Orchestrator([a]).run("salom", "single")[0], seen

    def test_chat_through_gateway(self):
        r, seen = self._chat()
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.text, "Salom shlyuzdan")
        self.assertEqual(seen[0]["model"], "llama-free")

    def test_falls_back_when_model_rejects_tools(self):
        for status in (400, 422):
            r, seen = self._chat(chat_status=status)
            self.assertTrue(r.ok, (status, r.error))
            self.assertEqual(r.text, "Salom shlyuzdan")
            self.assertIn("tools", seen[0])
            self.assertNotIn("tools", seen[-1])


if __name__ == "__main__":
    unittest.main()
