from __future__ import annotations

import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from .orchestrator import MODES, Orchestrator

MODE_HELP = {
    "auto": "Eng mos agentni o'zi tanlaydi",
    "single": "Tanlangan birinchi agent",
    "broadcast": "Hammasi parallel javob beradi",
    "pipeline": "Agentlar ketma-ket yaxshilaydi",
    "consensus": "Hammasi + hakam yakuniy javob tuzadi",
}


class App(tk.Tk):
    def __init__(self, orch: Orchestrator):
        super().__init__()
        self.orch = orch
        self.title("Agent Umimiy — barcha AI agentlar bir joyda")
        self.geometry("980x680")

        side = ttk.Frame(self, padding=8)
        side.pack(side="left", fill="y")
        ttk.Label(side, text="Agentlar", font=("", 11, "bold")).pack(anchor="w")
        self.vars = {}
        for name, agent in orch.agents.items():
            v = tk.BooleanVar(value=True)
            self.vars[name] = v
            ttk.Checkbutton(side, text=f"{name} ({agent.kind})", variable=v).pack(anchor="w")

        ttk.Label(side, text="Rejim", font=("", 11, "bold")).pack(anchor="w", pady=(14, 0))
        self.mode = tk.StringVar(value="auto")
        for m in MODES:
            ttk.Radiobutton(side, text=m, value=m, variable=self.mode, command=self._hint).pack(anchor="w")
        self.hint = ttk.Label(side, text=MODE_HELP["auto"], wraplength=170, foreground="#555")
        self.hint.pack(anchor="w", pady=4)
        ttk.Button(side, text="Suhbatni tozalash", command=self._clear).pack(fill="x", pady=(14, 0))

        main = ttk.Frame(self, padding=8)
        main.pack(side="right", fill="both", expand=True)
        self.out = scrolledtext.ScrolledText(main, wrap="word", state="disabled")
        self.out.pack(fill="both", expand=True)
        self.out.tag_configure("me", foreground="#0a58ca", font=("", 10, "bold"))
        self.out.tag_configure("agent", foreground="#198754", font=("", 10, "bold"))
        self.out.tag_configure("err", foreground="#dc3545")

        row = ttk.Frame(main)
        row.pack(fill="x", pady=(8, 0))
        self.entry = tk.Text(row, height=3, wrap="word")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Control-Return>", lambda e: (self.send(), "break")[1])
        self.btn = ttk.Button(row, text="Yuborish\n(Ctrl+Enter)", command=self.send)
        self.btn.pack(side="right", padx=(8, 0))
        self.entry.focus()

    def _hint(self):
        self.hint.config(text=MODE_HELP[self.mode.get()])

    def _clear(self):
        self.orch.reset()
        self._write("", clear=True)

    def _write(self, text, tag=None, clear=False):
        self.out.config(state="normal")
        if clear:
            self.out.delete("1.0", "end")
        self.out.insert("end", text, tag)
        self.out.see("end")
        self.out.config(state="disabled")

    def send(self):
        prompt = self.entry.get("1.0", "end").strip()
        if not prompt:
            return
        targets = [n for n, v in self.vars.items() if v.get()]
        if not targets:
            self._write("Kamida bitta agentni tanlang.\n", "err")
            return
        self.entry.delete("1.0", "end")
        self._write(f"\nSiz: {prompt}\n", "me")
        self.btn.state(["disabled"])
        mode = self.mode.get()
        threading.Thread(target=self._work, args=(prompt, mode, targets), daemon=True).start()

    def _work(self, prompt, mode, targets):
        try:
            results = self.orch.run(prompt, mode, targets)
        except Exception as exc:
            self.after(0, self._done, [], str(exc))
            return
        self.after(0, self._done, results, "")

    def _done(self, results, error):
        if error:
            self._write(f"Xato: {error}\n", "err")
        for r in results:
            self._write(f"\n● {r.agent} ({r.seconds:.1f}s)\n", "agent")
            if r.ok:
                self._write(r.text + "\n")
            else:
                self._write(f"Xato: {r.error}\n", "err")
        self.btn.state(["!disabled"])


def run(orch: Orchestrator):
    App(orch).mainloop()
