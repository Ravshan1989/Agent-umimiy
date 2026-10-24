from __future__ import annotations

import copy
import math
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import config, detect, theme
from .providers import build_agent
from .theme import P, Avatar, Pill, color_for, font, label, rrect

MODES = {
    "auto": ("✦", "Avtomatik", "Eng mos agentni o'zi tanlaydi"),
    "single": ("◉", "Bitta agent", "Tanlangan birinchi agent javob beradi"),
    "broadcast": ("⇉", "Hammasi birga", "Barcha agentlar bir vaqtda javob beradi"),
    "pipeline": ("⇢", "Ketma-ket", "Har bir agent oldingisining javobini yaxshilaydi"),
    "consensus": ("⚖", "Kengash", "Hammasi javob beradi, hakam yagona xulosa chiqaradi"),
}
TYPE_LABELS = {
    "anthropic": "Claude (API kalit kerak)",
    "openai": "ChatGPT / OpenAI-mos (API kalit)",
    "gemini": "Google Gemini (API kalit)",
    "ollama": "Lokal model — Ollama",
    "cli": "Kompyuterdagi dastur (CLI)",
}
SHORT_TYPE = {"anthropic": "Claude", "openai": "OpenAI-mos", "gemini": "Gemini", "ollama": "Lokal · Ollama",
              "cli": "Dastur (CLI)", "echo": "Demo"}
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o", "gemini": "gemini-2.0-flash", "ollama": "llama3"}
LABEL_TO_TYPE = {v: k for k, v in TYPE_LABELS.items()}
SUGGESTIONS = ["Bu kodni tushuntirib ber", "Menga qisqa xat yozib ber", "Ingliz tiliga tarjima qil",
               "G'oyalar bo'yicha maslahat ber"]


def _wrapped_lines(lines, f, px):
    """Matn necha qatorga o'ralishini so'z bo'yicha hisoblaydi."""
    sp, total = f.measure(" "), 0
    for line in lines:
        n, cur = 1, 0
        for word in line.split(" "):
            wl = f.measure(word)
            if cur == 0:
                cur = wl
            elif cur + sp + wl <= px:
                cur += sp + wl
            else:
                n, cur = n + 1, wl
        total += n
    return max(1, total)


def dark_top(parent, title, size=None):
    top = tk.Toplevel(parent)
    top.title(title)
    top.configure(bg=P["bg"])
    if size:
        top.geometry(size)
    top.transient(parent)
    return top


class AgentDialog(tk.Toplevel):
    """Bitta agentni qo'shish/tahrirlash — JSON yozish shart emas."""

    def __init__(self, parent, spec=None):
        super().__init__(parent)
        self.title("Agent sozlamasi")
        self.configure(bg=P["bg"])
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        spec = spec or {}
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack()
        label(f, "Agent sozlamasi", size=14, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.vars = {}
        rows = [("name", "Nomi"), ("type", "Turi"), ("model", "Model"), ("api_key", "API kalit"),
                ("base_url", "Manzil (ixtiyoriy)"), ("command", "Buyruq (CLI uchun)")]
        for i, (k, text) in enumerate(rows, start=1):
            label(f, text, fg=P["muted"]).grid(row=i, column=0, sticky="w", pady=5)
            v = tk.StringVar(value=spec.get(k, ""))
            if k == "type":
                v.set(TYPE_LABELS.get(spec.get("type", "anthropic"), TYPE_LABELS["anthropic"]))
                w = ttk.Combobox(f, textvariable=v, values=list(TYPE_LABELS.values()), state="readonly", width=38)
                w.bind("<<ComboboxSelected>>", lambda e: self._hint())
            else:
                w = ttk.Entry(f, textvariable=v, width=40, show="•" if k == "api_key" else "")
            w.grid(row=i, column=1, pady=5, padx=(12, 0))
            self.vars[k] = v
        self.hint = label(f, "", fg=P["muted"], size=9, wraplength=380, justify="left")
        self.hint.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        self._hint()
        btns = tk.Frame(f, bg=P["bg"])
        btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e")
        Pill(btns, "Bekor", self.destroy, width=90).pack(side="left", padx=4)
        Pill(btns, "Sinab ko'rish", self._test, width=130, outline=P["line"], bg=P["bg"]).pack(side="left", padx=4)
        Pill(btns, "Saqlash", self._save, width=110, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(side="left")
        self.grab_set()

    def _type(self):
        return LABEL_TO_TYPE.get(self.vars["type"].get(), "anthropic")

    def _hint(self):
        self.hint.config(text={
            "anthropic": "Kalitni console.anthropic.com dan oling. Model bo'sh qolsa, standarti ishlatiladi.",
            "openai": "OpenAI, OpenRouter, Groq yoki LM Studio. Lokal bo'lsa manzilni yozing: http://localhost:1234/v1",
            "gemini": "Kalitni aistudio.google.com dan oling.",
            "ollama": "Avval ollama.com dan o'rnating va modelni yuklab oling. Kalit shart emas.",
            "cli": "Masalan: codex exec {prompt}  yoki  claude -p {prompt}",
        }[self._type()])

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
        self.configure(bg=P["bg"])
        self.cfg, self.on_save = cfg, on_save
        self.geometry("680x560")
        self.transient(parent)
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack(fill="both", expand=True)
        label(f, "Agentlaringiz", size=15, weight="bold").pack(anchor="w")
        label(f, "Qo'shing, tahrirlang yoki vaqtincha o'chirib qo'ying", fg=P["muted"], size=9).pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(f, columns=("type", "model", "on"), show="headings", height=8)
        for c, t, w in (("type", "Agent", 250), ("model", "Model / buyruq", 220), ("on", "Yoqilgan", 80)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True)
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=12)
        for text, cmd, w in (("+ Qo'shish", self.add, 100), ("Tahrirlash", self.edit, 100), ("O'chirish", self.remove, 90),
                             ("Yoq / o'chir", self.toggle, 110), ("Avto-topish", self.autodetect, 110)):
            Pill(row, text, cmd, width=w, height=34, size=9).pack(side="left", padx=(0, 6))
        jr = tk.Frame(f, bg=P["bg"])
        jr.pack(fill="x")
        label(jr, "Kengashda hakam:", fg=P["muted"]).pack(side="left")
        self.judge = tk.StringVar(value=cfg.get("judge", ""))
        self.judge_box = ttk.Combobox(jr, textvariable=self.judge, state="readonly", width=24)
        self.judge_box.pack(side="left", padx=10)
        Pill(f, "Saqlash va yopish", self.save, width=170, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(
            anchor="e", pady=(14, 0))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self.cfg["agents"]):
            self.tree.insert("", "end", iid=str(i), values=(
                f"{a['name']}  ·  {SHORT_TYPE.get(a['type'], a['type'])}",
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


class ModeRow(tk.Canvas):
    def __init__(self, parent, key, on_pick):
        super().__init__(parent, height=40, bg=P["side"], highlightthickness=0, cursor="hand2")
        self.key, self.on_pick, self.active, self.over = key, on_pick, False, False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", lambda e: on_pick(key))
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))

    def _h(self, v):
        self.over = v
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        icon, title, _ = MODES[self.key]
        if self.active:
            rrect(self, 0, 0, w, h, 12, fill=P["card_hi"], outline=P["accent"])
        elif self.over:
            rrect(self, 0, 0, w, h, 12, fill=P["card"], outline="")
        self.create_text(22, h / 2, text=icon, fill=P["accent_hi"] if self.active else P["muted"], font=font(13))
        self.create_text(46, h / 2, text=title, anchor="w", fill=P["text"] if self.active else P["muted"],
                         font=font(10, "bold" if self.active else "normal"))


class AgentRow(tk.Canvas):
    def __init__(self, parent, agent, on_toggle):
        super().__init__(parent, height=48, bg=P["side"], highlightthickness=0, cursor="hand2")
        self.agent, self.on_toggle, self.on, self.over = agent, on_toggle, True, False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", lambda e: on_toggle(agent.name))
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))

    def _h(self, v):
        self.over = v
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if self.over:
            rrect(self, 0, 0, w, h, 12, fill=P["card"], outline="")
        c = color_for(self.agent.name)
        self.create_oval(8, h / 2 - 15, 38, h / 2 + 15, fill=c if self.on else P["line"], outline="")
        self.create_text(23, h / 2, text=self.agent.name[:1].upper(), fill="white", font=font(11, "bold"))
        self.create_text(50, h / 2 - 8, text=self.agent.name, anchor="w", font=font(10, "bold"),
                         fill=P["text"] if self.on else P["muted"])
        self.create_text(50, h / 2 + 9, text=SHORT_TYPE.get(self.agent.kind, self.agent.kind), anchor="w",
                         font=font(8), fill=P["muted"])
        self.create_oval(w - 22, h / 2 - 5, w - 12, h / 2 + 5, fill=P["ok"] if self.on else "", outline=P["ok"] if self.on else P["muted"], width=1)


class App(tk.Tk):
    PAD = 14

    def __init__(self, cfg_path: str | None = None):
        super().__init__()
        theme.setup(self)
        self.cfg_path = cfg_path
        self.inbox: queue.Queue = queue.Queue()
        self.cfg = config.read(cfg_path)
        first_run = not config.config_path(cfg_path).exists()
        self.title("Agent Umimiy")
        self.geometry("1180x780")
        self.minsize(860, 560)
        self.mode = tk.StringVar(value="auto")
        self.selected: set[str] = set()
        self.busy = False
        self.typing = None
        self.empty = None
        self.ph_on = False
        self._build_sidebar()
        self._build_main()
        self.rebuild()
        if first_run:
            self.after(400, self.first_run)

    # ---------- qurilish ----------
    def _build_sidebar(self):
        side = tk.Frame(self, bg=P["side"], width=290)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        inner = tk.Frame(side, bg=P["side"], padx=16, pady=18)
        inner.pack(fill="both", expand=True)

        logo = tk.Frame(inner, bg=P["side"])
        logo.pack(fill="x", pady=(0, 18))
        c = tk.Canvas(logo, width=42, height=42, bg=P["side"], highlightthickness=0)
        rrect(c, 0, 0, 42, 42, 13, fill=P["accent"], outline="")
        c.create_text(21, 21, text="A", fill="white", font=font(17, "bold"))
        c.pack(side="left")
        t = tk.Frame(logo, bg=P["side"])
        t.pack(side="left", padx=12)
        label(t, "Agent Umimiy", size=14, weight="bold").pack(anchor="w")
        label(t, "Barcha AI bir joyda", fg=P["muted"], size=9).pack(anchor="w")

        label(inner, "REJIM", fg=P["muted"], size=8, weight="bold").pack(anchor="w", pady=(4, 6))
        self.mode_rows = {}
        for k in MODES:
            r = ModeRow(inner, k, self.pick_mode)
            r.pack(fill="x", pady=1)
            self.mode_rows[k] = r

        label(inner, "AGENTLAR", fg=P["muted"], size=8, weight="bold").pack(anchor="w", pady=(18, 6))
        bottom = tk.Frame(inner, bg=P["side"])
        bottom.pack(side="bottom", fill="x")
        Pill(bottom, "＋  Yangi suhbat", self.new_chat, bg=P["accent"], hover=P["accent_hi"], fg="white",
             height=42, radius=14).pack(fill="x", pady=(0, 8))
        Pill(bottom, "⚙   Sozlamalar", self.open_settings, bg=P["card"], hover=P["card_hi"],
             height=42, radius=14).pack(fill="x")
        self.agent_box = tk.Frame(inner, bg=P["side"])
        self.agent_box.pack(fill="both", expand=True)

    def _build_main(self):
        main = tk.Frame(self, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        head = tk.Frame(main, bg=P["bg"], padx=28, pady=14)
        head.pack(fill="x")
        left = tk.Frame(head, bg=P["bg"])
        left.pack(side="left")
        self.title_lbl = label(left, "", size=15, weight="bold")
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = label(left, "", fg=P["muted"], size=9)
        self.sub_lbl.pack(anchor="w")
        self.count_lbl = tk.Label(head, text="", fg=P["ok"], bg=P["card"], font=font(9, "bold"), padx=12, pady=5)
        self.count_lbl.pack(side="right")
        tk.Frame(main, bg=P["line"], height=1).pack(fill="x")

        wrap = tk.Frame(main, bg=P["bg"])
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=P["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=P["bg"])
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel)

        self.wrap = tk.Canvas(main, bg=P["bg"], height=72, highlightthickness=0)
        self.wrap.pack(fill="x", padx=28, pady=(8, 20))
        self.entry = tk.Text(self.wrap, height=1, wrap="word", bg=P["card"], fg=P["text"], insertbackground=P["text"],
                             relief="flat", bd=0, highlightthickness=0, font=font(11), padx=2, pady=2)
        self.send_btn = tk.Canvas(self.wrap, width=44, height=44, bg=P["card"], highlightthickness=0, cursor="hand2")
        self.send_btn.bind("<Button-1>", lambda e: self.send())
        self.send_btn.bind("<Enter>", lambda e: self._send_draw(True))
        self.send_btn.bind("<Leave>", lambda e: self._send_draw(False))
        self._send_draw(False)
        self.wrap.bind("<Configure>", lambda e: self._layout_input())
        self.entry.bind("<Return>", self._enter)
        self.entry.bind("<KeyRelease>", lambda e: self._grow())
        self.entry.bind("<FocusIn>", lambda e: self._ph(False))
        self.entry.bind("<FocusOut>", lambda e: self._ph(True))
        self._ph(True)

    def _wheel(self, e):
        if self.canvas.yview() == (0.0, 1.0):
            return
        step = -1 if (e.num == 4 or e.delta > 0) else 1
        self.canvas.yview_scroll(step * 3, "units")

    # ---------- kiritish maydoni ----------
    def _send_draw(self, over):
        c = self.send_btn
        c.delete("all")
        col = P["muted"] if self.busy else (P["accent_hi"] if over else P["accent"])
        c.create_oval(2, 2, 42, 42, fill=col, outline="")
        c.create_text(22, 22, text="↑", fill="white", font=font(17, "bold"))

    def _layout_input(self):
        w, h = self.wrap.winfo_width(), self.wrap.winfo_height()
        self.wrap.delete("all")
        rrect(self.wrap, 1, 1, w - 1, h - 1, 26, fill=P["card"], outline=P["line"])
        self.wrap.create_window(22, h / 2, window=self.entry, anchor="w", width=max(50, w - 100), height=h - 26)
        self.wrap.create_window(w - 30, h / 2, window=self.send_btn)

    def _ph(self, show):
        text = self.entry.get("1.0", "end").strip()
        if show and not text:
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", "Xabar yozing…   (Enter — yuborish, Shift+Enter — yangi qator)")
            self.entry.config(fg=P["muted"])
            self.ph_on = True
        elif not show and self.ph_on:
            self.entry.delete("1.0", "end")
            self.entry.config(fg=P["text"])
            self.ph_on = False

    def _text(self):
        return "" if self.ph_on else self.entry.get("1.0", "end").strip()

    def _grow(self):
        n = self.entry.count("1.0", "end", "displaylines")
        lines = max(1, min(6, (n[0] if n else 1) - 0))
        self.wrap.configure(height=44 + lines * 22 if lines > 1 else 72)

    def _enter(self, e):
        if e.state & 0x1:
            return None
        self.send()
        return "break"

    # ---------- holat ----------
    def pick_mode(self, key):
        self.mode.set(key)
        for k, r in self.mode_rows.items():
            r.active = k == key
            r.draw()
        _, title, desc = MODES[key]
        self.title_lbl.config(text=title)
        self.sub_lbl.config(text=desc)

    def toggle_agent(self, name):
        if name in self.selected and len(self.selected) > 1:
            self.selected.discard(name)
        else:
            self.selected.add(name)
        for r in self.agent_box.winfo_children():
            r.on = r.agent.name in self.selected
            r.draw()
        self._count()

    def _count(self):
        self.count_lbl.config(text=f"●  {len(self.selected)} agent faol")

    def rebuild(self):
        self.orch = config.build(self.cfg)
        self.selected = set(self.orch.agents)
        for w in self.agent_box.winfo_children():
            w.destroy()
        for a in self.orch.agents.values():
            AgentRow(self.agent_box, a, self.toggle_agent).pack(fill="x", pady=1)
        self.pick_mode(self.mode.get())
        self._count()
        self.new_chat()

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
        Settings(self, copy.deepcopy(self.cfg), self.save_settings)

    def save_settings(self, cfg):
        self.cfg = cfg
        config.write(cfg, self.cfg_path)
        self.rebuild()

    # ---------- chat ----------
    def new_chat(self):
        self.orch.reset()
        self.typing = None
        for w in self.inner.winfo_children():
            w.destroy()
        self._show_empty()

    def _show_empty(self):
        demo = list(self.orch.agents) == ["demo"]
        box = tk.Frame(self.inner, bg=P["bg"])
        box.pack(pady=(90, 0))
        c = tk.Canvas(box, width=72, height=72, bg=P["bg"], highlightthickness=0)
        rrect(c, 0, 0, 72, 72, 22, fill=P["accent"], outline="")
        c.create_text(36, 36, text="A", fill="white", font=font(30, "bold"))
        c.pack()
        label(box, "Qanday yordam bera olaman?", size=22, weight="bold").pack(pady=(18, 4))
        label(box, "Agent sozlanmagan — chap pastdagi «Sozlamalar» orqali qo'shing." if demo else
              "Savolingizni yozing — agentlaringiz birgalikda javob beradi.", fg=P["muted"], size=11).pack()
        chips = tk.Frame(box, bg=P["bg"])
        chips.pack(pady=26)
        for i, s in enumerate(SUGGESTIONS):
            Pill(chips, s, lambda s=s: self._use_suggestion(s), width=250, height=44, radius=16, size=10,
                 weight="normal", outline=P["line"]).grid(row=i // 2, column=i % 2, padx=6, pady=6)
        self.empty = box

    def _use_suggestion(self, text):
        self._ph(False)
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", text)
        self.entry.focus_set()

    def _max_w(self):
        return int(max(320, min(760, self.canvas.winfo_width() * 0.68)))

    def _bubble(self, parent, text, bg, fg, outline=""):
        P_ = self.PAD
        c = tk.Canvas(parent, bg=parent["bg"], highlightthickness=0)
        f = font(11)
        t = tk.Text(c, wrap="word", bg=bg, fg=fg, relief="flat", bd=0, highlightthickness=0, font=f,
                    padx=0, pady=0, spacing1=1, spacing3=3, cursor="xterm", selectbackground=P["accent"])
        t.tag_configure("b", font=font(11, "bold"))
        t.tag_configure("code", font=font(10, mono=True), background=P["code"], foreground="#c9d1ff",
                        lmargin1=8, lmargin2=8, rmargin=8, spacing1=2, spacing3=2)
        plain = []
        for i, part in enumerate(re.split(r"```[\w+-]*\n?(.*?)```", text, flags=re.S)):
            if i % 2:
                t.insert("end", part.strip("\n"), "code")
                plain.append(part.strip("\n"))
                t.insert("end", "\n")
            else:
                for j, seg in enumerate(re.split(r"\*\*(.+?)\*\*", part)):
                    t.insert("end", seg, "b" if j % 2 else "")
                    plain.append(seg)
        if t.get("end-2c", "end-1c") == "\n":
            t.delete("end-2c", "end-1c")
        t.config(state="disabled")
        lines = "".join(plain).split("\n")
        w = max(60, min(self._max_w(), max((f.measure(x) for x in lines), default=0) + 16))
        zero = f.measure("0")
        chars = max(6, int(w / zero) + 1)
        t.config(width=chars, height=_wrapped_lines(lines, f, chars * zero))
        c.create_window(P_, P_, window=t, anchor="nw")
        t.update_idletasks()
        W, H = t.winfo_reqwidth() + 2 * P_, t.winfo_reqheight() + 2 * P_
        c.config(width=W, height=H)
        rrect(c, 1, 1, W - 1, H - 1, 18, fill=bg, outline=outline, tags="bg")
        c.tag_lower("bg")

        def refit(_e=None):  # ekranda paydo bo'lgach aniq balandlikka moslash
            n = t.count("1.0", "end", "displaylines")
            if n and n[0] != int(t.cget("height")):
                t.config(height=max(1, n[0]))
                t.update_idletasks()
                h2 = t.winfo_reqheight() + 2 * P_
                c.config(height=h2)
                c.delete("bg")
                rrect(c, 1, 1, W - 1, h2 - 1, 18, fill=bg, outline=outline, tags="bg")
                c.tag_lower("bg")
        c.bind("<Map>", lambda e: c.after(40, refit), add="+")
        t.bind("<Button-1>", lambda e: t.focus_set())
        menu = tk.Menu(t, tearoff=0, bg=P["card"], fg=P["text"], activebackground=P["accent"], bd=0)
        menu.add_command(label="Nusxalash", command=lambda: self._copy(text))
        t.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        return c

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _clear_empty(self):
        if self.empty is not None:
            self.empty.destroy()
            self.empty = None

    def add_user(self, text):
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        self._bubble(row, text, P["user"], "white").pack(side="right")
        self._scroll()

    def add_agent(self, name, text, meta="", err=False):
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        Avatar(row, name).pack(side="left", anchor="n", padx=(0, 12))
        col = tk.Frame(row, bg=P["bg"])
        col.pack(side="left", anchor="w")
        head = tk.Frame(col, bg=P["bg"])
        head.pack(anchor="w")
        label(head, name, fg=P["err"] if err else color_for(name.split(" ")[0]), size=10, weight="bold").pack(side="left")
        if meta:
            label(head, "   " + meta, fg=P["muted"], size=9).pack(side="left")
        self._bubble(col, text, "#2a1519" if err else P["card"], P["err"] if err else P["text"],
                     outline="#5b2530" if err else P["line"]).pack(anchor="w", pady=(5, 0))
        if not err:
            cp = label(col, "Nusxalash", fg=P["muted"], size=8, cursor="hand2")
            cp.pack(anchor="w", pady=(3, 0))
            cp.bind("<Button-1>", lambda e, t=text, w=cp: (self._copy(t), w.config(text="Nusxalandi ✓", fg=P["ok"])))
        self._scroll()

    def _scroll(self):
        self.update_idletasks()
        self.canvas.yview_moveto(1)
        self.after(150, lambda: self.canvas.yview_moveto(1))  # pufakcha aniq o'lchamga kelgach

    def _typing_on(self, names):
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        self.dots = label(row, "", fg=P["accent_hi"], size=14, weight="bold")
        self.dots.pack(side="left", padx=(46, 0))
        self.who = label(row, "  " + ", ".join(names) + " yozmoqda…", fg=P["muted"], size=9)
        self.who.pack(side="left")
        self.typing = row
        self._tick(0)
        self._scroll()

    def _tick(self, i):
        if self.typing is None:
            return
        self.dots.config(text=["●○○", "○●○", "○○●"][i % 3])
        self.after(280, self._tick, i + 1)

    def send(self):
        if self.busy:
            return
        prompt = self._text()
        if not prompt:
            return
        self.entry.delete("1.0", "end")
        self._grow()
        self.add_user(prompt)
        mode = self.mode.get()
        targets = [n for n in self.orch.agents if n in self.selected]
        shown = targets[:1] if mode == "single" else targets
        self.busy = True
        self._send_draw(False)
        self._typing_on(shown)
        self.after(100, self._poll)
        threading.Thread(target=self._work, args=(prompt, mode, targets), daemon=True).start()

    def _work(self, prompt, mode, targets):
        try:
            res, err = self.orch.run(prompt, mode, targets), ""
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
        if self.typing is not None:
            self.typing.destroy()
            self.typing = None
        if error:
            self.add_agent("Xato", error, err=True)
        for r in results:
            if r.ok:
                self.add_agent(r.agent, r.text or "(bo'sh javob)", f"{r.seconds:.1f} s")
            else:
                self.add_agent(r.agent, r.error, "xato", err=True)
        self.busy = False
        self._send_draw(False)
        self.entry.focus_set()


def run(cfg_path: str | None = None):
    App(cfg_path).mainloop()
