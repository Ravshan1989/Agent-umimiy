import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from rms_ai import config, server
from rms_ai.store import Store

PASSWORD = "parol12345"


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        cfg = self.d / "agents.json"
        cfg.write_text(json.dumps({"web": False, "agents": [{"name": "aks", "type": "echo"}]}))
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)
        self.store = Store(self.d / "server.db")
        self.httpd = server.create(self.store, config_file=str(cfg))
        self.app = self.httpd.app
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.store.close)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.app.shutdown, 0)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.cookie = ""

    def call(self, path: str, body=None):
        headers = {"Cookie": self.cookie}
        data = None
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, headers=headers), timeout=10) as r:
                if r.headers.get("Set-Cookie"):
                    self.cookie = r.headers["Set-Cookie"].split(";")[0]
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def register(self):
        code, _ = self.call("/api/register", {"name": "ali", "password": PASSWORD, "invite": self.store.invite().lower()})
        self.assertEqual(code, 200)

    def test_requests_are_counted_with_user_and_time(self):
        self.register()
        for _ in range(3):
            self.assertEqual(self.call("/api/me")[0], 200)
        self.assertEqual(self.call("/api/yoq-yol")[0], 404)
        data = self.app.monitor()
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["last_minute"], 5)
        me = next(p for p in data["paths"] if p["path"] == "GET /api/me")
        self.assertEqual(me["count"], 3)
        self.assertGreaterEqual(me["p95"], me["median"])
        self.assertGreater(me["max"], 0)
        ali = next(u for u in data["users"] if u["user"] == "ali")
        self.assertEqual((ali["ip"], ali["requests"]), ("127.0.0.1", 4))  # register javobida hali sessiya yo'q edi
        self.assertEqual(data["recent"][0]["code"], 404)

    def test_query_string_secrets_never_reach_memory_or_log_file(self):
        self.call("/api/desktop-login?token=JUDA-MAXFIY")
        self.call("/client-enter?key=BOSHQA-MAXFIY")
        self.assertNotIn("MAXFIY", json.dumps(self.app.monitor()))
        self.app.shutdown(0)  # log faylini yopadi
        text = (self.d / "requests.log").read_text(encoding="utf-8")
        self.assertIn("/api/desktop-login", text)
        self.assertNotIn("MAXFIY", text)
        self.assertEqual(len(text.splitlines()[0].split("\t")), 7)

    def test_dashboard_is_owner_only_and_excludes_itself(self):
        self.assertEqual(self.call("/api/desktop/monitor")[0], 401)  # sessiyasiz
        self.register()
        self.assertEqual(self.call("/api/desktop/monitor")[0], 404)  # veb-foydalanuvchi: desktop emas
        self.assertEqual(self.call("/monitor")[0], 404)
        self.assertEqual(self.call("/api/desktop/monitor/open", {})[0], 404)
        self.app.desktop = True  # dasturning o'z oynasi
        code, page = self.call("/monitor")
        self.assertEqual(code, 200)
        self.assertIn(b"Monitoring", page)
        before = self.app.monitor()["total"]
        code, raw = self.call("/api/desktop/monitor")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["total"], before)  # dashboard so'rovi o'zini sanamaydi
        self.assertEqual(self.app.monitor()["total"], before)

    def test_memory_is_bounded(self):
        for i in range(server.METRICS_KEEP + 50):
            self.app.record_request("10.0.0.1", "x", "GET", "/p", 200, float(i))
        self.assertEqual(len(self.app.metrics), server.METRICS_KEEP)
        self.assertEqual(self.app.monitor()["total"], server.METRICS_KEEP + 50)


if __name__ == "__main__":
    unittest.main()
