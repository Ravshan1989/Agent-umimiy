"""Resurslar (fayl, SQLite ulanishi, fon xizmatlari) to'g'ri yopilishini tekshiruvchi testlar."""
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from rms_ai import config, detect, discovery, rag, server
from rms_ai.store import Store


class ServerStopTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        cfg = self.d / "agents.json"
        cfg.write_text(json.dumps({"web": False, "agents": [{"name": "aks", "type": "echo"}]}))
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)
        self.httpd = server.create(Store(self.d / "server.db"), config_file=str(cfg))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def test_stop_shuts_down_app_services_and_closes_request_log(self):
        """GUI'da veb-server o'chirilganda agentlar, MCP, rejalashtiruvchi va log fayli ham yopilishi kerak."""
        app = self.httpd.app
        app.record_request("127.0.0.1", "test", "GET", "/", 200, 1.0)
        handler = app.request_log.handlers[0]
        self.assertIsNotNone(handler.stream)  # yozuvdan keyin fayl ochiq
        mcp_manager = mock.Mock()
        app.mcp_manager = mcp_manager
        with mock.patch("rms_ai.browser.shutdown") as browsers:
            server.stop(self.httpd)
        self.assertIsNone(handler.stream)
        mcp_manager.shutdown.assert_called_once()
        self.assertTrue(app.scheduler._stop.is_set())
        browsers.assert_not_called()  # klassik oyna brauzeri yopilib qolmaydi

    def test_stop_can_close_shared_browsers_when_asked(self):
        with mock.patch("rms_ai.browser.shutdown") as browsers:
            server.stop(self.httpd, close_browsers=True)
        browsers.assert_called_once()


class SqliteConnectionTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        patch = mock.patch.object(config, "user_dir", return_value=self.d)
        patch.start()
        self.addCleanup(patch.stop)

    def _tracking_connect(self):
        opened: list[sqlite3.Connection] = []
        real = sqlite3.connect

        def connect(*args, **kwargs):
            conn = real(*args, **kwargs)
            opened.append(conn)
            return conn

        return opened, connect

    @staticmethod
    def _is_closed(conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            return True
        return False

    def test_rag_connections_are_closed(self):
        project = self.d / "loyiha"
        project.mkdir()
        (project / "eslatma.md").write_text("Shartnoma muddati 2027 yilgacha", encoding="utf-8")
        opened, connect = self._tracking_connect()
        with mock.patch.object(rag.sqlite3, "connect", side_effect=connect):
            self.assertEqual(rag.index_project(str(project))["indexed"], 1)
            self.assertEqual(rag.search("shartnoma")[0]["name"], "eslatma.md")
            self.assertEqual(rag.stats()["indexed"], 1)
        self.assertEqual(len(opened), 3)
        self.assertTrue(all(self._is_closed(c) for c in opened))

    def test_rag_rolls_back_failed_index(self):
        project = self.d / "loyiha"
        project.mkdir()
        (project / "a.md").write_text("birinchi matn", encoding="utf-8")
        rag.index_project(str(project))
        with mock.patch.object(rag, "_extract_text", side_effect=RuntimeError("buzildi")), \
                self.assertRaises(RuntimeError):
            rag.index_project(str(project))
        self.assertEqual(rag.stats()["indexed"], 1)  # eski indeks yo'qolmaydi

    def test_detect_freellm_key_closes_connection(self):
        db = self.d / "freellm" / "server" / "data" / "freeapi.db"
        db.parent.mkdir(parents=True)
        with sqlite3.connect(str(db)) as setup:
            setup.execute("CREATE TABLE settings (key TEXT, value TEXT)")
            setup.execute("INSERT INTO settings VALUES ('unified_api_key', 'kalit-1')")
        setup.close()
        opened, connect = self._tracking_connect()
        # Muhitni to'liq tozalamaymiz: Windows'da Path.home() USERPROFILE ga tayanadi.
        with mock.patch.dict("os.environ", {"RMS_AI_LLM_DIR": str(self.d)}), \
                mock.patch("sqlite3.connect", side_effect=connect):
            for name in ("FREELLMAPI_API_KEY", "FREELLMAPI_KEY"):
                os.environ.pop(name, None)
            key = detect.freellmapi_key()
        self.assertEqual(key, "kalit-1")
        self.assertTrue(opened and all(self._is_closed(c) for c in opened))


class DiscoveryStopRaceTests(unittest.TestCase):
    def test_stop_while_answering_does_not_crash_thread(self):
        """stop() soketni None qilgan paytda oqim javob yuborayotgan bo'lsa ham AttributeError bo'lmasligi kerak."""
        responder = discovery.DiscoveryResponder(http_port=8080)

        class FakeSock:
            def recvfrom(self, _n):
                responder.stop()  # aynan so'rov kelgan paytda boshqa oqim to'xtatadi
                return discovery.DISCOVERY_MAGIC, ("127.0.0.1", 1)

            def sendto(self, *_a):
                raise AssertionError("to'xtatilgandan keyin javob yuborilmasligi kerak")

            def close(self):
                pass

        responder._sock = FakeSock()
        responder._loop()  # istisno chiqmasdan tugashi kerak
        self.assertIsNone(responder._sock)


if __name__ == "__main__":
    unittest.main()
