import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_umimiy import chatstore, config, markdown
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from agent_umimiy.tools import Context, Toolbox, system_prompt


class MarkdownTests(unittest.TestCase):
    def test_blocks_and_inline(self):
        segs = markdown.parse("# Sarlavha\n- bir **qalin**\n- ikki `kod`\n[sayt](https://a.uz/x)\n```py\nx = 1\n```\nOxiri")
        d = {t: tags for t, tags in segs}
        self.assertEqual(d["Sarlavha"], ("h1",))
        self.assertEqual(d["qalin"], ("b",))
        self.assertEqual(d["kod"], ("ic",))
        self.assertEqual(d["sayt"], ("link:https://a.uz/x",))
        self.assertEqual(d["x = 1\n"], ("code",))
        text = markdown.plain(segs)
        self.assertIn("• bir qalin", text)
        self.assertNotIn("**", text)
        self.assertNotIn("```", text)
        self.assertFalse(text.endswith("\n"))

    def test_table_and_plain(self):
        segs = markdown.parse("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertTrue(all(tags == ("table",) for t, tags in segs if t.strip()))
        self.assertEqual(markdown.plain(markdown.parse("oddiy matn")), "oddiy matn")

    def test_bad_markup_survives(self):
        for s in ("**", "``", "[x](", "***a**", "# ", "```kod yopilmagan"):
            markdown.parse(s)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        p = mock.patch.object(config, "user_dir", return_value=self.d)
        p.start()
        self.addCleanup(p.stop)

    def chat(self, n, title="t"):
        return {"title": title, "project": "", "history": [{"role": "user", "content": str(i)} for i in range(n)],
                "records": [{"k": "user", "text": str(i)} for i in range(n)]}

    def test_roundtrip_and_limits(self):
        chatstore.save([self.chat(200), self.chat(0, "bo'sh")], 5)
        data = chatstore.load()
        self.assertEqual(len(data["chats"]), 1)  # bo'sh suhbat saqlanmaydi
        self.assertEqual(len(data["chats"][0]["records"]), chatstore.MAX_RECORDS)
        self.assertEqual(len(data["chats"][0]["history"]), chatstore.MAX_HISTORY)
        self.assertEqual(data["active"], 0)
        chatstore.clear()
        self.assertEqual(chatstore.load()["chats"], [])

    def test_corrupt_file_is_ignored(self):
        (self.d / "chats.json").write_text("{buzilgan")
        self.assertEqual(chatstore.load(), {"chats": [], "active": 0})


class InstructionsAndTodo(unittest.TestCase):
    def test_project_instructions_in_system_prompt(self):
        d = tempfile.mkdtemp()
        self.assertNotIn("Project instructions", system_prompt(Context(root=d)))
        (Path(d) / "CLAUDE.md").write_text("Testlarni doim pytest bilan yozing.")
        sp = system_prompt(Context(root=d))
        self.assertIn("pytest", sp)
        self.assertIn("never override", sp)

    def test_todo_tool_emits_list(self):
        got = []
        tb = Toolbox(Context(emit=lambda a, k, t: got.append((k, t))), "x")
        out, err = tb.run("todo_write", {"todos": [{"content": "bir", "status": "completed"},
                                                    {"content": "ikki", "status": "in_progress"}]})
        self.assertFalse(err)
        self.assertEqual(got[0][0], "todo")
        self.assertEqual(json.loads(got[0][1])[1]["status"], "in_progress")

    def test_history_is_capped(self):
        o = Orchestrator([build_agent({"name": "e", "type": "echo"})])
        for i in range(60):
            o.run(f"q{i}", "single")
        self.assertLessEqual(len(o.history), 40)
        self.assertEqual(o.history[0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
