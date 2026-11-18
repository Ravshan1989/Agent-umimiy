import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from rms_ai import discovery, server


class TestDiscovery(unittest.TestCase):
    def test_udp_responder_and_discover(self):
        responder = discovery.DiscoveryResponder(http_port=8080, discovery_port=48180)
        responder.start()
        try:
            found = discovery.discover_server(timeout=1.2, discovery_port=48180)
            self.assertIsNotNone(found)
            self.assertEqual(found["port"], 8080)
            self.assertIn(":8080/", found["url"])
        finally:
            responder.stop()

    def test_resolve_falls_back_to_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "server.json"
            discovery.save_cached_server(
                {"ip": "127.0.0.1", "port": 8080, "host": "localhost", "url": "http://127.0.0.1:8080/"},
                cache_path=cache,
            )
            with mock.patch.object(discovery, "discover_server", return_value=None):
                with mock.patch.object(discovery, "probe_url", return_value=True):
                    resolved = discovery.resolve_server(timeout=0.1, cache_path=cache)
                    self.assertIsNotNone(resolved)
                    self.assertEqual(resolved["port"], 8080)

    def test_web_access_false_blocks_browser_allows_client(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = Path(tmp) / "agents.json"
            cfg_path.write_text(json.dumps({"web_access": False, "agents": []}), encoding="utf-8")
            httpd = server.start("127.0.0.1", 0, str(cfg_path))
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                base = f"http://127.0.0.1:{httpd.server_port}"
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(base + "/", timeout=3)
                ctx.exception.close()
                self.assertEqual(ctx.exception.code, 403)

                cj = http.cookiejar.CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                resp = opener.open(f"{base}/client-enter?key={httpd.app.client_key}", timeout=3)
                self.assertEqual(resp.status, 200)
            finally:
                httpd.shutdown()
                httpd.server_close()
                httpd.app.shutdown()
                httpd.store.close()


if __name__ == "__main__":
    unittest.main()
