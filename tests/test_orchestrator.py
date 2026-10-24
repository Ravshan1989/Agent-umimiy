import json
import sys
import unittest

from agent_umimiy import config
from agent_umimiy.orchestrator import Orchestrator
from agent_umimiy.providers import CLIAgent, EchoAgent, build_agent


class Boom(EchoAgent):
    def _ask(self, prompt, history):
        raise RuntimeError("buzildi")


def make():
    return Orchestrator(
        [EchoAgent("a"), EchoAgent("b", prefix="B:")],
        judge="a",
        routes={"b": ["kod"]},
    )


class Tests(unittest.TestCase):
    def test_auto_routes_by_keyword(self):
        self.assertEqual(make().run("kod yoz", "auto")[0].agent, "b")
        self.assertEqual(make().run("salom", "auto")[0].agent, "a")

    def test_broadcast(self):
        self.assertEqual({r.agent for r in make().run("x", "broadcast")}, {"a", "b"})

    def test_pipeline_passes_output(self):
        r = make().run("x", "pipeline")
        self.assertIn("Oldingi agent (a)", r[1].text)

    def test_consensus_adds_final(self):
        r = make().run("x", "consensus")
        self.assertEqual(r[-1].agent, "a (yakuniy)")

    def test_failure_isolated(self):
        o = Orchestrator([Boom("bad"), EchoAgent("ok")])
        r = o.run("x", "broadcast")
        self.assertFalse(r[0].ok)
        self.assertTrue(r[1].ok)

    def test_history_kept_and_reset(self):
        o = make()
        o.run("x", "single")
        self.assertEqual(len(o.history), 2)
        o.reset()
        self.assertEqual(o.history, [])

    def test_cli_agent_stdin_and_arg(self):
        a = CLIAgent("c", command=f"{sys.executable} -c \"import sys;print(sys.stdin.read().upper())\"")
        self.assertEqual(a.ask("salom").text, "SALOM")
        b = CLIAgent("d", command=f"{sys.executable} -c \"import sys;print(sys.argv[1])\" {{prompt}}")
        self.assertEqual(b.ask("hi there").text, "hi there")

    def test_missing_api_key_reports_error(self):
        r = build_agent({"name": "x", "type": "openai", "api_key_env": "NO_SUCH_KEY_XYZ"}).ask("hi")
        self.assertFalse(r.ok)
        self.assertIn("NO_SUCH_KEY_XYZ", r.error)

    def test_example_config_loads(self):
        o = config.load("agents.example.json")
        self.assertIn("claude", o.agents)


if __name__ == "__main__":
    unittest.main()
