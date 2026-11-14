import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agent_umimiy import memory, stream
from agent_umimiy.agentic import _text_tool_calls
from agent_umimiy.base import AgentError
from agent_umimiy.providers import EchoAgent
from agent_umimiy.tools import Context


class HttpErrorPrefix(unittest.TestCase):
    def test_friendly_text_keeps_status_prefix(self):
        body = json.dumps({"error": {"message": "model not found"}})
        text = stream._friendly_http_error(404, body)
        self.assertTrue(text.startswith("HTTP 404: "))
        self.assertIn("topilmadi", text)
        for status in (401, 402, 429, 500):
            self.assertTrue(stream._friendly_http_error(status, "x").startswith(f"HTTP {status}: "))

    def test_image_endpoint_branch_keeps_prefix(self):
        body = json.dumps({"error": {"message": "No endpoints found that support image input"}})
        text = stream._friendly_http_error(404, body)
        self.assertTrue(text.startswith("HTTP 404: "))
        self.assertIn("rasm", text)

    def test_ask_falls_back_to_plain_chat_on_404(self):
        class ToolAgent(EchoAgent):
            supports_tools = True

            def _ask_tools(self, prompt, history, tb):
                raise AgentError(stream._friendly_http_error(404, '{"error": {"message": "endpoint"}}'), status=404)

        with tempfile.TemporaryDirectory() as d:
            ctx = Context(root=d)
            r = ToolAgent("t").ask("salom", [], ctx)
        self.assertTrue(r.ok, r.error)
        self.assertIn("salom", r.text)

    def test_ask_does_not_fall_back_on_401(self):
        class ToolAgent(EchoAgent):
            supports_tools = True

            def _ask_tools(self, prompt, history, tb):
                raise AgentError(stream._friendly_http_error(401, "bad key"), status=401)

        with tempfile.TemporaryDirectory() as d:
            ctx = Context(root=d)
            r = ToolAgent("t").ask("salom", [], ctx)
        self.assertFalse(r.ok)
        self.assertTrue(r.error.startswith("HTTP 401: "))


class MemorySafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.json"
        patcher = mock.patch.object(memory, "_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_corrupt_file_is_not_overwritten(self):
        self.path.write_text('[{"id": "a1", "fact": "muhim"}', encoding="utf-8")  # buzilgan JSON
        before = self.path.read_bytes()
        out = memory.remember("yangi fakt")
        self.assertIn("o'qilmadi", out)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn("o'qilmadi", memory.forget("a1"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.path.with_name("memory.json.bad").exists())

    def test_bom_file_is_read(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps([{"id": "a1", "fact": "Toshkent shahri"}]).encode())
        self.assertIn("a1", memory.search("Toshkent"))
        self.assertIn("Xotiraga saqlandi", memory.remember("ikkinchi fakt"))
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))), 2)

    def test_search_no_match_and_empty_query(self):
        memory.remember("kofe yoqadi")
        self.assertEqual(memory.search("samolyot"), "Xotirada mos ma'lumot yo'q.")
        self.assertIn("kofe", memory.search(""))
        self.assertIn("kofe", memory.search("kofe", limit="ko'p"))  # raqam emas — xato bermaydi


def _tool(name, **props):
    return SimpleNamespace(name=name, parameters={"properties": {k: {"type": v} for k, v in props.items()}})


class TextToolCalls(unittest.TestCase):
    tools = [_tool("write_file", path="string", content="string", overwrite="boolean", count="integer")]

    def _args(self, text):
        calls = _text_tool_calls(text, self.tools)
        self.assertEqual(len(calls), 1)
        return json.loads(calls[0]["function"]["arguments"])

    def test_string_values_not_stripped(self):
        args = self._args('<function_calls><invoke name="write_file">'
                          '<parameter name="content">\n  a\n</parameter></invoke></function_calls>')
        self.assertEqual(args["content"], "\n  a\n")

    def test_raw_lt_and_amp_fall_back_to_regex(self):
        args = self._args('<function_calls><invoke name="write_file"><parameter name="path">a.py</parameter>'
                          '<parameter name="content">if a < b && c:\n    pass</parameter>'
                          '<parameter name="count"> 3 </parameter></invoke></function_calls>')
        self.assertEqual(args, {"path": "a.py", "content": "if a < b && c:\n    pass", "count": 3})

    def test_python_booleans_and_raw_fallback(self):
        args = self._args('<function_calls><invoke name="write_file"><parameter name="overwrite">True</parameter>'
                          '<parameter name="count">ko\'p</parameter></invoke></function_calls>')
        self.assertIs(args["overwrite"], True)
        self.assertEqual(args["count"], "ko'p")


if __name__ == "__main__":
    unittest.main()
