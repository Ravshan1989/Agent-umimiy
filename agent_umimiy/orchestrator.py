from __future__ import annotations

import copy
import dataclasses
import re
from concurrent.futures import ThreadPoolExecutor

from . import attachments
from .base import Agent, Result
from .tools import Context

MODES = ("auto", "single", "broadcast", "pipeline", "consensus")
READ_ONLY_MODES = ("broadcast", "consensus")
MAX_AGENTS = 16
_STOP_WORDS = set("a an and are as at be bir bilan bu buni uchun from ga ham in is it kerak like men meniga mi my of on or odam this the to u va yoki uchun you siz men unda nima qanaqa qanday qil ber kerak bo'ladi shuni shu bilan uchun yana".split())


def _terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[\w+#.-]+", str(text or "").lower())
            if len(word) > 2 and word not in _STOP_WORDS}


def _matches(term: str, profile: set[str]) -> bool:
    return any(term == candidate or term.startswith(candidate) or candidate.startswith(term)
               for candidate in profile if min(len(term), len(candidate)) >= 4)


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
        if len(agents) > MAX_AGENTS:
            raise ValueError(f"Bir loyihada ko'pi bilan {MAX_AGENTS} ta agent ishlatish mumkin.")
        if len({a.name for a in agents}) != len(agents):
            raise ValueError("Agent nomlari takrorlanmasligi kerak.")
        self.agents = {a.name: a for a in agents}
        self.judge = judge or agents[0].name
        self.routes = routes or {}  # {"agent": ["kalit", "so'z"]}
        self.history: list[dict] = []
        self.ctx = Context(roster=[{"name": a.name, "kind": a.kind, "model": a.options.get("model", ""),
                                    "description": a.description} for a in agents],
                           delegate=self._delegate)

    def _delegate(self, name: str, prompt: str, frm: str) -> str:
        """Bir agent boshqasidan yordam so'raydi: o'qiy oladi, o'zgartira olmaydi, o'zi yana so'ray olmaydi."""
        target = self._get(name)
        if target.kind == "cli":
            raise ValueError("Xavfsizlik uchun CLI agentni boshqa agent nomidan chaqirib bo'lmaydi.")
        child = dataclasses.replace(self.ctx, readonly=True, delegate=None, always=set())
        r = copy.copy(target).ask(f"[{frm} agent sizdan so'rayapti]\\n{prompt}", [], child, None)
        return r.text if r.ok else f"[{name} javob bera olmadi: {r.error}]"

    def reset(self):
        self.history.clear()

    def _get(self, name: str) -> Agent:
        if name not in self.agents:
            raise KeyError(f"Agent topilmadi: {name}")
        return self.agents[name]

    def pick(self, prompt: str, pool: list[Agent] | None = None, files: list | None = None) -> Agent:
        pool = pool or list(self.agents.values())
        allowed = {a.name for a in pool}
        task = _terms(prompt)
        if any(getattr(file, "kind", "") == "image" for file in files or []):
            task |= _terms("rasm skrinshot surat image vision")
        best, score = None, 0
        for name, words in self.routes.items():
            s = sum(any(term.startswith(w.lower()) or w.lower().startswith(term) for term in task)
                    for w in words)
            if s > score and name in allowed:
                best, score = name, s
        if best:
            return self.agents[best]

        # If the user has described an agent's specialty, prefer the closest
        # match to the task over the first item in the list.
        ranked = []
        for agent in pool:
            description = _terms(agent.description)
            identity = _terms(f"{agent.name} {agent.options.get('model', '')}")
            if agent.kind == "ollama":
                description |= _terms("mahalliy lokal offline internet yo'q maxfiy shaxsiy")
            points = sum(3 for term in task if _matches(term, description))
            points += sum(1 for term in task if _matches(term, identity))
            ranked.append((points, agent))
        top_score = max((points for points, _ in ranked), default=0)
        if top_score:
            return next(agent for points, agent in ranked if points == top_score)
        # Mos yo'nalish ham, tavsif ham yo'q (masalan oddiy "salom"): lokal Ollama agenti
        # birinchi o'ringa chiqadi — u tarmoqsiz, tez ishlaydi va bepul bulut shlyuzidagi
        # kechikish/limitlarga bog'liq emas. Keyin sinov (echo) bo'lmagan haqiqiy agent.
        return (next((a for a in pool if a.kind == "ollama"), None)
                or next((a for a in pool if a.kind != "echo"), pool[0]))

    @staticmethod
    def _cancelled(result: Result) -> bool:
        return any(word in result.error.lower() for word in ("to'xtatildi", "cancelled", "canceled"))

    def _ask_with_fallback(self, first: Agent, prompt: str, history: list[dict], ctx: Context,
                           files: list, fallback_pool: list[Agent]) -> list[Result]:
        """Xato bo'lsa, bekor qilishdan tashqari, qolgan AI provayderlarni navbat bilan sinaydi."""
        results = [first.ask(prompt, history, ctx, files)]
        if results[0].ok or self._cancelled(results[0]):
            return results
        attempted = {first.name}
        for agent in fallback_pool:
            if agent.name in attempted or agent.kind in ("echo", "cli"):
                continue
            attempted.add(agent.name)
            result = agent.ask(prompt, history, ctx, files)
            results.append(result)
            if result.ok:
                break
        return results

    def run(self, prompt: str, mode: str = "auto", targets: list[str] | None = None, files=None) -> list[Result]:
        files = list(files or [])
        if mode not in MODES:
            raise ValueError(f"Noma'lum rejim: {mode}")
        names = list(dict.fromkeys(targets)) if targets else list(self.agents)
        agents = [self._get(n) for n in names]
        if mode in READ_ONLY_MODES:
            agents = [a for a in agents if a.kind != "cli"]
            if not agents:
                raise ValueError("Faqat o'qish rejimida CLI agent ishlatilmaydi; API agentni tanlang.")
        self.ctx.cancel.clear()
        if self.ctx.mcp:
            self.ctx.mcp.wait_ready(8)  # plaginlar hali ulanayotgan bo'lsa, biroz kutamiz
        self.ctx.readonly = mode in READ_ONLY_MODES  # bir nechta agent bir vaqtda fayl o'zgartirmasligi uchun

        if mode == "auto":
            first = self.pick(prompt, agents, files)
            results = self._ask_with_fallback(first, prompt, self.history, self.ctx, files, agents)
        elif mode == "single":
            # Single tanlovda ham provider limiti tugasa, loyihadagi keyingi API agentga o'tamiz.
            results = self._ask_with_fallback(agents[0], prompt, self.history, self.ctx, files,
                                             list(self.agents.values()))
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
                judge = next((a for a in agents if a.name == self.judge), agents[0])
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
