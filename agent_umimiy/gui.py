from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import config, detect
from .orchestrator import MODES
from .providers import build_agent

MODE_LABELS = {
    "auto": "Avtomatik (o'zi tanlaydi)",
    "single": "Bitta agent",
    "broadcast": "Hammasi bir vaqtda",
    "pipeline": "Ketma-ket (yaxshilab boradi)",
    "consensus": "Kengash (hakam xulosa qiladi)",
}
TYPE_LABELS = {
    "anthropic": "Claude (API kalit kerak)",
    "openai": "ChatGPT / OpenAI-mos (API kalit)",
    "gemini": "Google Gemini (API kalit)",
    "ollama": "Lokal model — Ollama",
    "cli": "Kompyuterdagi dastur (CLI)",
}
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o", "gemini": "gemini-2.0-flash", "ollama": "llama3"}
LABEL_TO_MODE = {v: k for k, v in MODE_LABELS.items()}
LABEL_TO_TYPE = {v: k for k, v in TYPE_LABELS.items()}

BG, USER_BG, BOT_BG = "#f4f5f7", "#d6e8ff", "#ffffff"


class AgentDialog(tk.Toplevel):
    """Bitta agentni qo'shish/tahrirlash — JSON yozish shart emas."""

    def __init__(self, parent, spec=None):
        super().__init__(parent)
        self.title("Agent sozlamasi")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        spec = spec or {}
        f = ttk.Frame(self, padding=14)
        f.pack()
        self.vars = {}
        rows = [("name", "Nomi"), ("type", "Turi"), ("model", "Model"), ("api_key", "API kalit"),
                ("base_url", "Manzil (ixtiyoriy)"), ("command", "Buyruq (CLI uchun)")]
        for i, (k, label) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=spec.get(k, ""))
            if k == "type":
                v.set(TYPE_LABELS.get(spec.get("type", "anthropic")))
                w = ttk.Combobox(f, textvariable=v, values=list(TYPE_LABELS.values()), state="readonly", width=38)
                w.bind("<<ComboboxSelected>>", lambda e: self._hint())
            else:
                w = ttk.Entry(f, textvariable=v, width=40, show="•" if k == "api_key" else "")
            w.grid(row=i, column=1, pady=3, padx=(8, 0))
            self.vars[k] = v
        self.hint = ttk.Label(f, foreground="#666", wraplength=330, justify="left")
        self.hint.grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=6)
        self._hint()
        btns = ttk.Frame(f)
        btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Sinab ko'rish", command=self._test).pack(side="left", padx=4)
        ttk.Button(btns, text="Saqlash", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Bekor", command=self.destroy).pack(side="left")
        self.grab_set()

    def _type(self):
        return LABEL_TO_TYPE.get(self.vars["type"].get(), "anthropic")

    def _hint(self):
        t = self._type()
        self.hint.config(text={
            "anthropic": "Kalitni console.anthropic.com dan oling. Model bo'sh qolsa, standart ishlatiladi.",
            "openai": "OpenAI, OpenRouter, Groq yoki LM Studio. Lokal bo'lsa manzilni yozing: http://localhost:1234/v1",
            "gemini": "Kalitni aistudio.google.com dan oling.",
            "ollama": "Avval ollama.com dan o'rnating va modelni yuklab oling. Kalit shart emas.",
            "cli": "Masalan: codex exec {prompt}  yoki  claude -p {prompt}",
        }[t])

    def _spec(self):
        t = self._type()
        s = {"name": self.vars["name"].get().strip(), "type": t}
        for k in ("model", "api_key", "base_url", "command"):
            val = self.vars[k].get().strip()
            if val:
                s[k] = val
        if "model" not in s and t in DEFAULT_MODEL:
            s["model"] = DEFAULT_MODEL[t]
        return s

    def _test(self):
        s = self._spec()
        if not s["name"]:
            return messagebox.showwarning("Diqqat", "Nomini yozing", parent=self)
        self.config(cursor="watch")
        self.update()
        r = build_agent(s).ask("Salom! Bir so'z bilan javob ber.")
        self.config(cursor="")
        if r.ok:
            messagebox.showinfo("Ishlayapti ✓", r.text[:300], parent=self)
        else:
            messagebox.showerror("Xato", r.error, parent=self)

    def _save(self):
        s = self._spec()
        if not s["name"]:
            return messagebox.showwarning("Diqqat", "Nomini yozing", parent=self)
        if s["type"] == "cli" and not s.get("command"):
            return messagebox.showwarning("Diqqat", "Buyruqni yozing", parent=self)
        self.result = s
        self.destroy()


class Settings(tk.Toplevel):
    def __init__(self, parent, cfg, on_save):
        super().__init__(parent)
        self.title("Sozlamalar")
        self.cfg, self.on_save = cfg, on_save
        self.geometry("560x420")
        self.transient(parent)
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Agentlaringiz", font=("", 12, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(f, columns=("type", "model", "on"), show="headings", height=10)
        for c, t, w in (("type", "Turi", 200), ("model", "Model / buyruq", 220), ("on", "Yoqilgan", 70)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, pady=6)
        row = ttk.Frame(f)
        row.pack(fill="x")
        for text, cmd in (("➕ Qo'shish", self.add), ("✏️ Tahrirlash", self.edit), ("🗑 O'chirish", self.remove),
                          ("⏯ Yoq/o'chir", self.toggle), ("🔍 Avto-topish", self.autodetect)):
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=2)
        jr = ttk.Frame(f)
        jr.pack(fill="x", pady=(10, 0))
        ttk.Label(jr, text="Kengashda hakam:").pack(side="left")
        self.judge = tk.StringVar(value=cfg.get("judge", ""))
        self.judge_box = ttk.Combobox(jr, textvariable=self.judge, state="readonly", width=24)
        self.judge_box.pack(side="left", padx=6)
        ttk.Button(f, text="Saqlash va yopish", command=self.save).pack(anchor="e", pady=(10, 0))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self.cfg["agents"]):
            self.tree.insert("", "end", iid=str(i), values=(
                f"{a['name']} — {TYPE_LABELS.get(a['type'], a['type'])}",
                a.get("model") or a.get("command", ""), "ha" if a.get("enabled", True) else "yo'q"))
        self.judge_box["values"] = [a["name"] for a in self.cfg["agents"]]

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def add(self):
        d = AgentDialog(self)
        self.wait_window(d)
        if d.result:
            self.cfg["agents"].append(d.result)
            self.refresh()

    def edit(self):
        i = self._sel()
        if i is None:
            return
        d = AgentDialog(self, self.cfg["agents"][i])
        self.wait_window(d)
        if d.result:
            d.result["enabled"] = self.cfg["agents"][i].get("enabled", True)
            self.cfg["agents"][i] = d.result
            self.refresh()

    def remove(self):
        i = self._sel()
        if i is not None and messagebox.askyesno("O'chirish", "Bu agent o'chirilsinmi?", parent=self):
            del self.cfg["agents"][i]
            self.refresh()

    def toggle(self):
        i = self._sel()
        if i is not None:
            a = self.cfg["agents"][i]
            a["enabled"] = not a.get("enabled", True)
            self.refresh()

    def autodetect(self):
        have = {a["name"] for a in self.cfg["agents"]}
        new = [a for a in detect.discover() if a["name"] not in have]
        self.cfg["agents"] += new
        self.refresh()
        messagebox.showinfo("Avto-topish", f"{len(new)} ta yangi agent topildi." if new else
                            "Yangi agent topilmadi. Ollama/LM Studio ishga tushirilganini tekshiring.", parent=self)

    def save(self):
        self.cfg["judge"] = self.judge.get()
        self.on_save(self.cfg)
        self.destroy()


class App(tk.Tk):
    def __init__(self, cfg_path: str | None = None):
        super().__init__()
        self.cfg_path = cfg_path
        self.inbox: queue.Queue = queue.Queue()
        self.cfg = config.read(cfg_path)
        first_run = not config.config_path(cfg_path).exists()
        self.title("Agent Umimiy")
        self.geometry("900x700")
        self.configure(bg=BG)

        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Rejim:").pack(side="left")
        self.mode = tk.StringVar(value=MODE_LABELS["auto"])
        ttk.Combobox(bar, textvariable=self.mode, values=list(MODE_LABELS.values()), state="readonly",
                     width=32).pack(side="left", padx=6)
        self.agent_lbl = ttk.Label(bar, foreground="#555")
        self.agent_lbl.pack(side="left", padx=10)
        ttk.Button(bar, text="⚙ Sozlamalar", command=self.open_settings).pack(side="right")
        ttk.Button(bar, text="🧹 Yangi suhbat", command=self.new_chat).pack(side="right", padx=6)

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        row = ttk.Frame(self, padding=10)
        row.pack(fill="x")
        self.entry = tk.Text(row, height=3, wrap="word", font=("", 11))
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._enter)
        self.btn = ttk.Button(row, text="Yuborish ➤", command=self.send)
        self.btn.pack(side="right", padx=(8, 0), ipady=10)

        self.rebuild()
        self.entry.focus()
        if first_run:
            self.after(300, self.first_run)

    # --- sozlash ---
    def rebuild(self):
        self.orch = config.build(self.cfg)
        names = ", ".join(self.orch.agents)
        self.agent_lbl.config(text=f"Agentlar: {names}")
        self.new_chat(greet=True)

    def first_run(self):
        found = detect.discover()
        if found:
            names = "\n".join("• " + a["name"] for a in found)
            if messagebox.askyesno("Xush kelibsiz!", f"Kompyuteringizda quyidagi agentlar topildi:\n\n{names}\n\n"
                                   "Hammasini qo'shaymi?", parent=self):
                self.cfg["agents"] += found
                config.write(self.cfg, self.cfg_path)
                return self.rebuild()
        messagebox.showinfo("Xush kelibsiz!", "Boshlash uchun «Sozlamalar» da agent qo'shing "
                            "(Claude, ChatGPT, Gemini yoki lokal model).", parent=self)
        self.open_settings()

    def open_settings(self):
        import copy
        Settings(self, copy.deepcopy(self.cfg), self.save_settings)

    def save_settings(self, cfg):
        self.cfg = cfg
        config.write(cfg, self.cfg_path)
        self.rebuild()

    # --- chat ---
    def new_chat(self, greet=False):
        self.orch.reset()
        for w in self.inner.winfo_children():
            w.destroy()
        if greet:
            demo = list(self.orch.agents) == ["demo"]
            self.bubble("Salom! Men Agent Umimiy — barcha AI agentlaringizni bitta chatda birlashtiraman. "
                        + ("Hozircha agent yo'q: ⚙ Sozlamalar orqali qo'shing." if demo else
                           "Savolingizni yozing, yuqoridan rejimni tanlashingiz mumkin."), "Agent Umimiy")

    def bubble(self, text, who, user=False, err=False):
        outer = tk.Frame(self.inner, bg=BG)
        outer.pack(fill="x", padx=12, pady=5)
        box = tk.Frame(outer, bg=USER_BG if user else BOT_BG, padx=10, pady=6)
        box.pack(anchor="e" if user else "w")
        tk.Label(box, text=who, font=("", 9, "bold"), bg=box["bg"], fg="#b00020" if err else "#198754" if not user
                 else "#0a58ca").pack(anchor="w")
        lines = text.count("\n") + len(text) // 80 + 1
        t = tk.Text(box, width=min(90, max(20, max(len(x) for x in text.split("\n")) + 2)),
                    height=min(lines, 40), wrap="word", relief="flat", bg=box["bg"], font=("", 11),
                    borderwidth=0, highlightthickness=0)
        t.insert("1.0", text)
        t.config(state="disabled")  # belgilab nusxalash mumkin
        t.pack()
        self.update_idletasks()
        self.canvas.yview_moveto(1)

    def _enter(self, e):
        if e.state & 0x1:  # Shift+Enter — yangi qator
            return None
        self.send()
        return "break"

    def send(self):
        prompt = self.entry.get("1.0", "end").strip()
        if not prompt:
            return
        self.entry.delete("1.0", "end")
        self.bubble(prompt, "Siz", user=True)
        self.btn.state(["disabled"])
        self.status = tk.Label(self.inner, text="⏳ Agent(lar) o'ylayapti...", bg=BG, fg="#777")
        self.status.pack(anchor="w", padx=14)
        mode = LABEL_TO_MODE[self.mode.get()]
        self.after(100, self._poll)
        threading.Thread(target=self._work, args=(prompt, mode), daemon=True).start()

    def _work(self, prompt, mode):
        try:
            res, err = self.orch.run(prompt, mode), ""
        except Exception as exc:
            res, err = [], str(exc)
        self.inbox.put((res, err))

    def _poll(self):
        try:
            res, err = self.inbox.get_nowait()
        except queue.Empty:
            return self.after(100, self._poll)
        self._done(res, err)

    def _done(self, results, error):
        self.status.destroy()
        if error:
            self.bubble(error, "Xato", err=True)
        for r in results:
            if r.ok:
                self.bubble(r.text or "(bo'sh javob)", f"{r.agent} · {r.seconds:.1f}s")
            else:
                self.bubble(r.error, f"{r.agent} — xato", err=True)
        self.btn.state(["!disabled"])
        self.entry.focus()


def run(cfg_path: str | None = None):
    App(cfg_path).mainloop()
