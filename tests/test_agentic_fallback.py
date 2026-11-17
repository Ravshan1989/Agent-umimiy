import unittest
from pathlib import Path
from unittest import mock

from rms_ai import agentic, tools
from rms_ai.base import AgentError


class AgenticFallbackTests(unittest.TestCase):
    def test_openai_falls_back_on_rate_limit_or_timeout(self):
        ctx = tools.Context(root=Path("."), allow_private=False, readonly=True)
        tb = tools.Toolbox(ctx, "freellmapi")
        seen_models = []

        def fake_stream(url, payload, headers, on_text):
            seen_models.append(payload["model"])
            if len(seen_models) == 1:
                raise AgentError("HTTP 429: Too Many Requests")
            on_text("Tayyor!")
            return {"role": "assistant", "content": "Tayyor!"}

        cfg = {
            "base_url": "http://127.0.0.1:3001/v1",
            "model": "llama-3.3-70b",
            "tools": True,
        }
        with mock.patch("rms_ai.stream.openai", side_effect=fake_stream):
            out = agentic.openai(cfg, "k", "Salom", [], tb)

        self.assertEqual(out, "Tayyor!")
        self.assertEqual(seen_models, ["llama-3.3-70b", "mistral-small-3.2-24b"])


if __name__ == "__main__":
    unittest.main()
