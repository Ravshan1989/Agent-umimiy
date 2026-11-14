"""Regression tests for persisted chat history."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_umimiy import chatstore


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.user_dir = Path(self.temp.name)
        self.patch_user_dir = patch("agent_umimiy.chatstore.config.user_dir", return_value=self.user_dir)
        self.patch_user_dir.start()
        self.addCleanup(self.patch_user_dir.stop)

    def test_save_and_load_preserve_selected_chat_after_invalid_entries(self):
        chats = [
            {"title": "first", "records": [{"k": "user", "text": "one"}], "history": []},
            {"title": "invalid", "records": "not-a-list", "history": []},
            {"title": "selected", "records": [{"k": "user", "text": "two"}], "history": []},
        ]
        chatstore.save(chats, 2)

        loaded = chatstore.load()
        self.assertEqual([c["title"] for c in loaded["chats"]], ["first", "selected"])
        self.assertEqual(loaded["active"], 1)

    def test_load_legacy_chat_payload_without_history_field(self):
        path = chatstore.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "active": 0,
            "chats": [{"title": "legacy", "records": [{"k": "user", "text": "hello"}]}],
        }), encoding="utf-8")

        loaded = chatstore.load()
        self.assertEqual(len(loaded["chats"]), 1)
        self.assertEqual(loaded["chats"][0]["title"], "legacy")
        self.assertEqual(loaded["chats"][0]["history"], [])

    def test_load_rejects_malformed_or_oversized_store(self):
        path = chatstore.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(chatstore.load(), {"chats": [], "active": 0})

        path.write_bytes(b"x" * (chatstore.MAX_CHATSTORE_BYTES + 1))
        self.assertEqual(chatstore.load(), {"chats": [], "active": 0})

    def test_active_boolean_is_not_treated_as_integer_index(self):
        path = chatstore.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "active": True,
            "chats": [{"records": [{"k": "user", "text": "hello"}], "history": []}],
        }), encoding="utf-8")
        self.assertEqual(chatstore.load()["active"], 0)

    def test_text_and_record_limits_are_applied(self):
        chats = [{
            "records": [{"k": "user", "text": "x" * (chatstore.MAX_TEXT_FIELD + 100)}],
            "history": [],
        }]
        chatstore.save(chats, 0)
        loaded = chatstore.load()
        self.assertEqual(len(loaded["chats"][0]["records"][0]["text"]), chatstore.MAX_TEXT_FIELD)


if __name__ == "__main__":
    unittest.main()
