import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rms_ai import config


class MigrationTests(unittest.TestCase):
    """Dastur nomi o'zgargach, avvalgi papkadagi ma'lumot yangi nomga ko'chishi kerak."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.old = self.base / config._OLD_DIR_NAMES["RMSAI"]

    def test_old_folder_is_renamed_with_its_data(self):
        self.old.mkdir()
        (self.old / "server.db").write_text("suhbatlar")
        path = config.migrated(self.base, "RMSAI")
        self.assertEqual(path, self.base / "RMSAI")
        self.assertEqual((path / "server.db").read_text(), "suhbatlar")
        self.assertFalse(self.old.exists())

    def test_plugin_commands_in_migrated_config_use_the_new_module(self):
        self.old.mkdir()
        (self.old / "agents.json").write_text(
            '{"mcp": [{"command": "python -m %s.builtin_mcp xotira"}]}' % config._OLD_MODULE, encoding="utf-8")
        path = config.migrated(self.base, "RMSAI")
        self.assertIn("python -m rms_ai.builtin_mcp xotira", (path / "agents.json").read_text(encoding="utf-8"))

    def test_existing_new_folder_is_never_overwritten(self):
        self.old.mkdir()
        (self.base / "RMSAI").mkdir()
        (self.base / "RMSAI" / "server.db").write_text("yangi")
        self.assertEqual(config.migrated(self.base, "RMSAI"), self.base / "RMSAI")
        self.assertEqual((self.base / "RMSAI" / "server.db").read_text(), "yangi")
        self.assertTrue(self.old.is_dir())

    def test_fresh_install_gets_the_new_name(self):
        self.assertEqual(config.migrated(self.base, "RMSAI"), self.base / "RMSAI")
        self.assertFalse(self.old.exists())

    def test_busy_old_folder_keeps_working_instead_of_starting_empty(self):
        self.old.mkdir()
        with mock.patch.object(Path, "rename", side_effect=PermissionError):
            self.assertEqual(config.migrated(self.base, "RMSAI"), self.old)

    def test_user_dir_migrates_on_first_call(self):
        self.old.mkdir()
        (self.old / "agents.json").write_text("{}")
        with mock.patch.dict("os.environ", {"APPDATA": str(self.base), "XDG_CONFIG_HOME": str(self.base)}), \
                mock.patch.object(config.sys, "platform", "win32"):
            path = config.user_dir()
        self.assertEqual(path.name, "RMSAI")
        self.assertTrue((path / "agents.json").is_file())


if __name__ == "__main__":
    unittest.main()
