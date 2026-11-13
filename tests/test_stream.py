import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from agent_umimiy import stream
from agent_umimiy.base import AgentError
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import build_agent
from tests.test_tools import serve


def raw_server(body: bytes, ctype: str = "text/event-stream"):
    """Har so'rovga bir xil tayyor javob beradigan soxta API."""
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}"


def run(spec: dict, on_event=None):
    events = []
    o = Orchestrator([build_agent({"name": "a", "api_key": "k", **spec})])
    o.ctx.web = False

    def emit(agent, kind, text):
        events.append((kind, text))
        if on_event:
            on_event(o, kind)
    o.ctx.emit = emit
    return o.run("salom", "single")[0], events


class OllamaArgumentRecoveryTests(unittest.TestCase):
    def test_invalid_tool_arguments_do_not_abort_turn(self):
        from agent_umimiy import agentic
        from agent_umimiy.tools import Context, Toolbox

        malformed = {"role": "assistant", "tool_calls": [
            {"function": {"name": "todo_write", "arguments": "{bad json"}}]}
        final = {"role": "assistant", "content": "Yakuniy javob"}
        tb = Toolbox(Context(), "sinov")
        with mock.patch("agent_umimiy.agentic.stream.ollama", side_effect=[malformed, final]):
            self.assertEqual(agentic.ollama({}, "Salom", [], tb), "Yakuniy javob")


class ToolFallbackTests(unittest.TestCase):
    def test_friendly_404_keeps_status_for_plain_chat_fallback(self):
        from agent_umimiy.base import Agent

        class NoToolAgent(Agent):
            supports_tools = True

            def _ask(self, prompt, history):
                return "Oddiy chat javobi"

            def _ask_tools(self, prompt, history, tb):
                raise AgentError("Tanlangan model yoki API manzili topilmadi.", status=404)

        agent = NoToolAgent("sinov")
        from agent_umimiy.tools import Context
        result = agent.ask("Salom", ctx=Context(web=True))
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.text, "Oddiy chat javobi")


class StreamTests(unittest.TestCase):
    def test_text_arrives_in_pieces_and_is_joined(self):
        for kind, resp in (("anthropic", {"content": [{"type": "text", "text": "Salom dunyo"}]}),
                           ("openai", {"choices": [{"message": {"content": "Salom dunyo"}}]})):
            srv, _ = serve([resp])
            r, events = run({"type": kind, "base_url": f"http://127.0.0.1:{srv.server_port}"})
            self.assertEqual(r.text, "Salom dunyo", kind)
            deltas = [t for k, t in events if k == "delta"]
            self.assertGreater(len(deltas), 1, kind)
            self.assertEqual("".join(deltas), "Salom dunyo", kind)

    def test_new_turn_after_tool_step(self):
        srv, _ = serve([{"content": [{"type": "text", "text": "Qarayman"},
                                     {"type": "tool_use", "id": "1", "name": "list_agents", "input": {}}]},
                        {"content": [{"type": "text", "text": "Tayyor"}]}])
        o = Orchestrator([build_agent({"name": "a", "type": "anthropic", "api_key": "k",
                                       "base_url": f"http://127.0.0.1:{srv.server_port}"})])
        events = []
        o.ctx.emit = lambda agent, kind, text: events.append(kind)
        self.assertEqual(o.run("x", "single")[0].text, "Tayyor")
        self.assertLess(events.index("turn"), len(events) - 1 - events[::-1].index("delta"))  # turn dan keyin yana matn keldi

    def test_gemini(self):
        chunks = [{"candidates": [{"content": {"parts": [{"text": t}]}}]} for t in ("Sal", "om")]
        base = raw_server("".join(f"data: {json.dumps(c)}\r\n\r\n" for c in chunks).encode())
        r, events = run({"type": "gemini", "base_url": base})
        self.assertEqual((r.text, [t for k, t in events if k == "delta"]), ("Salom", ["Sal", "om"]))

    def test_ollama(self):
        lines = [{"message": {"content": "Sal"}}, {"message": {"content": "om"}, "done": True}]
        base = raw_server("".join(json.dumps(x) + "\n" for x in lines).encode(), "application/x-ndjson")
        r, events = run({"type": "ollama", "base_url": base, "tools": False})
        self.assertEqual((r.text, [t for k, t in events if k == "delta"]), ("Salom", ["Sal", "om"]))

    def test_provider_response_size_is_bounded(self):
        base = raw_server(b"x" * (stream.MAX_LINE + 2) + b"\\n")
        with self.assertRaises(AgentError):
            list(stream._lines(base, {}, {}))
        base = raw_server(b"1234\\n5678\\n")
        with mock.patch.object(stream, "MAX_RESPONSE", 8):
            with self.assertRaises(AgentError):
                list(stream._lines(base, {}, {}))

    def test_stop_cuts_the_stream(self):
        srv, _ = serve([{"content": [{"type": "text", "text": "uzun javob matni"}]}])
        r, events = run({"type": "anthropic", "base_url": f"http://127.0.0.1:{srv.server_port}"},
                        on_event=lambda o, kind: o.ctx.cancel.set())
        self.assertEqual((r.ok, r.error), (False, "To'xtatildi"))
        self.assertEqual(len([k for k, _ in events if k == "delta"]), 1)

    def test_errors_are_reported(self):
        base = raw_server(b'data: {"type": "error", "error": {"message": "limit tugadi"}}\n\n')
        r, _ = run({"type": "anthropic", "base_url": base, "tools": False})
        self.assertIn("limit tugadi", r.error)
        base = raw_server(b'{"choices": [{"message": {"content": "oqimsiz"}}]}', "application/json")
        r, _ = run({"type": "openai", "base_url": base, "tools": False})
        self.assertIn("streaming", r.error)


if __name__ == "__main__":
    unittest.main()
