import io
import json
import unittest
from unittest import mock

from agent_umimiy import updater


class UpdaterTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertGreater(updater.parse_version("v0.7.3"), updater.parse_version("0.7.2"))
        self.assertGreater(updater.parse_version("0.10.0"), updater.parse_version("0.7.9"))
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3))

    def test_check_update_finds_newer_release(self):
        payload = json.dumps({
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/Ravshan1989/RMS-AI/releases/tag/v9.9.9",
            "body": "Yangi imkoniyatlar",
            "assets": [
                {"name": "RMSAI-Setup.exe", "browser_download_url": "https://github.com/Ravshan1989/RMS-AI/releases/download/v9.9.9/RMSAI-Setup.exe"}
            ],
        }).encode("utf-8")
        fake_resp = mock.MagicMock()
        fake_resp.read.return_value = payload
        fake_resp.__enter__.return_value = fake_resp
        with mock.patch("urllib.request.urlopen", return_value=fake_resp):
            res = updater.check_update("https://api.github.com/repos/Ravshan1989/RMS-AI/releases/latest")
        self.assertTrue(res["update_available"])
        self.assertEqual(res["latest_version"], "9.9.9")
        self.assertTrue(res["download_url"].endswith("RMSAI-Setup.exe"))
        self.assertEqual(res["error"], "")

    def test_check_update_rejects_non_https(self):
        res = updater.check_update("http://example.com/release.json")
        self.assertFalse(res["update_available"])
        self.assertIn("HTTPS", res["error"])

    def test_install_update_rejects_non_https(self):
        with self.assertRaises(ValueError):
            updater.install_update("http://example.com/RMSAI-Setup.exe")


if __name__ == "__main__":
    unittest.main()
