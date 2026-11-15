import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_umimiy import autostart


class TestAutostart(unittest.TestCase):
    def test_ensure_local_services_skips_when_ports_open(self):
        with mock.patch.object(autostart, "_is_port_open", return_value=True):
            with mock.patch.object(autostart, "_spawn_background") as sp:
                started = autostart.ensure_local_services(r"D:\nonexistent-llm")
                self.assertEqual(started, [])
                sp.assert_not_called()

    def test_ensure_local_services_starts_present_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "freellm" / "server" / "dist").mkdir(parents=True)
            (root / "freellm" / "server" / "dist" / "index.js").write_text("// ok")
            (root / ".venv" / "Scripts").mkdir(parents=True)
            (root / ".venv" / "Scripts" / "pythonw.exe").write_text("")
            (root / ".venv" / "Scripts" / "litellm.exe").write_text("")
            (root / "litellm_config.yaml").write_text("model_list: []\n")

            with mock.patch.object(autostart, "_is_port_open", return_value=False):
                with mock.patch.object(autostart.shutil, "which", side_effect=lambda name: f"{name}.exe"):
                    with mock.patch.object(autostart, "_spawn_background", return_value=True) as sp:
                        started = autostart.ensure_local_services(root)
                        self.assertIn("freellmapi", started)
                        self.assertIn("g4f", started)
                        self.assertIn("litellm", started)
                        self.assertGreaterEqual(sp.call_count, 3)


if __name__ == "__main__":
    unittest.main()
