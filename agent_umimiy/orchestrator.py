from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from . import attachments
from .base import Agent, Result
from .tools import Context

MODES = ("auto", "single", "broadcast", "pipeline", "consensus")
READ_ONLY_MODES = ("broadcast", "consensus")


class Orchestrator:
    """Barcha agentlarni boshqaradi.

    Rejimlar:
      single    — bitta tanlangan agent
      auto      — kalit so'zlar bo'yicha eng mos agentni tanlaydi
      broadcast — hamma agentga bir vaqtda so'rov yuboradi
      pipeline  — agentlar ketma-ket: oldingisining javobi keyingisiga beriladi
      consensus — hamma javob beradi, so'ng "hakam" agent yagona javob tuzadi
    """

    def __init__(self, agents: list[Agent], judge: str | None = None, routes: dict | None = None):
        if not agents:
            raise ValueError("Kamida bitta agent kerak")
        self.agents = {a.name: a for a in agents}
        self.judge = judge or agents[0].name
        self.routes = routes or {}  # {"agent": ["kalit", "so'z"]}
        self.history: list[dict] = []
        self.ctx = Context()

    def reset(self):
        self.history.clear()

    def _get(self, name: str) -> Agent:
        if name not in self.agents:
            raise KeyError(f"Agent topilmadi: {name}")
        return self.agents[name]

    def pick(self, prompt: str, pool: list[Agent] | None = None) -> Agent:
        pool = pool or list(self.agents.values())
        allowed = {a.name for a in pool}
        low = prompt.lower()
        best, score = None, 0
        for name, words in self.routes.items():
            s = sum(w.lower() in low for w in words)
            if s > score and name in allowed:
                best, score = name, s
        return self.agents[best] if best else pool[0]

    def run(self, prompt: str, mode: str = "auto", targets: list[str] | None = None, files=None) -> list[Result]:
        files = list(files or [])
        if mode not in MODES:
            raise ValueError(f"Noma'lum rejim: {mode}")
        agents = [self._get(n) for n in targets] if targets else list(self.agents.values())
        self.ctx.cancel.clear()
        self.ctx.readonly = mode in READ_ONLY_MODES  # bir nechta agent bir vaqtda fayl o'zgartirmasligi uchun

        if mode == "auto":
            results = [self.pick(prompt, agents).ask(prompt, self.history, self.ctx, files)]
        elif mode == "single":
            results = [agents[0].ask(prompt, self.history, self.ctx, files)]
        elif mode == "broadcast":
            results = self._parallel(agents, prompt, self.history, self.ctx, files)
        elif mode == "pipeline":
            results, current = [], prompt
            for a in agents:
                r = a.ask(current, self.history, self.ctx, files)
                results.append(r)
                if not r.ok:
                    break
                current = f"Asl so'rov: {prompt}\n\nOldingi agent ({r.agent}) javobi:\n{r.text}\n\nUni yaxshilab, davom ettir."
        else:  # consensus
            results = self._parallel(agents, prompt, self.history, self.ctx, files)
            good = [r for r in results if r.ok]
            if len(good) > 1:
                joined = "\n\n".join(f"--- {r.agent} ---\n{r.text}" for r in good)
                judge = self._get(self.judge)
                final = judge.ask(
                    f"Savol: {prompt}\n\nQuyidagi agentlar javob berdi:\n{joined}\n\n"
                    "Ularni solishtirib, eng to'g'ri va to'liq yagona javob tuz.",
                )
                final.agent = f"{judge.name} (yakuniy)"
                results.append(final)

        final = next((r for r in reversed(results) if r.ok), None)
        if final:
            self.history += [{"role": "user", "content": prompt + attachments.note(files)}, {"role": "assistant", "content": final.text}]
            self.history = self.history[-40:]  # kontekst cheksiz o'smasligi uchun
        return results

    @staticmethod
    def _parallel(agents: list[Agent], prompt: str, history=None, ctx=None, files=None) -> list[Result]:
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            return list(pool.map(lambda a: a.ask(prompt, history, ctx, files), agents))
