from __future__ import annotations

import contextlib
import copy
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import attachments, config, detect, gitutil, theme
from .orchestrator import READ_ONLY_MODES
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
PROJECT_SUGGESTIONS = ["Bu loyiha nima haqida? Qisqa tushuntirib ber", "Kodda xatolarni top va tuzat",
                       "README.md faylini yoz yoki yangila", "Testlarni ishga tushir, xato bo'lsa tuzat"]
KIND_ICON = {"read": "◧", "write": "✎", "run": "▶", "info": "•"}
KIND_COLOR = {"read": P["muted"], "write": P["warn"], "run": P["accent_hi"], "info": P["err"]}
SUGGESTIONS = ["Bu kodni tushuntirib ber", "Menga qisqa xat yozib ber", "Ingliz tiliga tarjima qil",
               "Internetdan bugungi yangiliklarni top"]


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
        self.geometry("680x600")
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
        self.web = tk.BooleanVar(value=cfg.get("web", True))
        tk.Checkbutton(f, text="Agentlar internetdan qidira va sahifalarni o'qiy olsin", variable=self.web, bg=P["bg"],
                       fg=P["text"], selectcolor=P["card"], activebackground=P["bg"], activeforeground=P["text"],
                       highlightthickness=0, bd=0, font=font(10)).pack(anchor="w", pady=(12, 0))
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
        self.cfg["web"] = bool(self.web.get())
        self.on_save(self.cfg)
        self.destroy()


class ApproveDialog(tk.Toplevel):
    """Agent fayl o'zgartirmoqchi yoki buyruq ishga tushirmoqchi bo'lganda ruxsat so'raydi."""

    def __init__(self, parent, agent, kind, title, detail):
        super().__init__(parent)
        self.title("Ruxsat kerak")
        self.configure(bg=P["bg"])
        self.transient(parent)
        self.result = "no"
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack(fill="both", expand=True)
        label(f, f"{agent} ruxsat so'ramoqda", fg=P["warn"], size=9, weight="bold").pack(anchor="w")
        label(f, title, size=13, weight="bold", wraplength=560, justify="left").pack(anchor="w", pady=(2, 10))
        box = tk.Text(f, width=76, height=14, bg=P["code"], fg="#c9d1ff", relief="flat", bd=0, font=font(10, mono=True),
                      padx=10, pady=8, wrap="none", highlightthickness=0)
        box.insert("1.0", detail)
        for i, line in enumerate(detail.split("\n"), 1):
            if line.startswith("+") and not line.startswith("+++"):
                box.tag_add("add", f"{i}.0", f"{i}.end")
            elif line.startswith("-") and not line.startswith("---"):
                box.tag_add("del", f"{i}.0", f"{i}.end")
        box.tag_config("add", foreground=P["ok"])
        box.tag_config("del", foreground=P["err"])
        box.config(state="disabled")
        box.pack(fill="both", expand=True)
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=(14, 0))
        always = "Shu suhbatda doim ruxsat" if kind == "write" else "Buyruqlarga doim ruxsat"
        Pill(row, "Rad etish", lambda: self._done("no"), width=110, fg=P["err"]).pack(side="left")
        Pill(row, "Ruxsat berish", lambda: self._done("yes"), width=140, bg=P["accent"], hover=P["accent_hi"],
             fg="white").pack(side="right")
        Pill(row, always, lambda: self._done("always"), width=190, outline=P["line"], bg=P["bg"]).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", lambda: self._done("no"))
        self.grab_set()
        self.focus_force()

    def _done(self, r):
        self.result = r
        self.destroy()


class GitDialog(tk.Toplevel):
    """Git ni oddiy tilda: nima o'zgargan, saqlash (commit), yuborish, olish."""

    def __init__(self, parent, root):
        super().__init__(parent)
        self.root_dir = root
        self.title("Git — o'zgarishlar")
        self.configure(bg=P["bg"])
        self.geometry("760x640")
        self.transient(parent)
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack(fill="both", expand=True)
        self.head = label(f, "", size=14, weight="bold")
        self.head.pack(anchor="w")
        self.sub = label(f, "", fg=P["muted"], size=9)
        self.sub.pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(f, columns=("what", "file"), show="headings", height=6)
        self.tree.heading("what", text="Holati")
        self.tree.heading("file", text="Fayl")
        self.tree.column("what", width=190)
        self.tree.column("file", width=480)
        self.tree.pack(fill="x")
        self.out = tk.Text(f, height=10, bg=P["code"], fg="#c9d1ff", relief="flat", bd=0, font=font(9, mono=True),
                           padx=10, pady=8, wrap="none", highlightthickness=0, state="disabled")
        self.out.tag_config("add", foreground=P["ok"])
        self.out.tag_config("del", foreground=P["err"])
        self.out.pack(fill="both", expand=True, pady=10)
        msg = tk.Frame(f, bg=P["bg"])
        msg.pack(fill="x")
        label(msg, "Saqlash izohi:", fg=P["muted"]).pack(side="left")
        self.msg = tk.StringVar()
        ttk.Entry(msg, textvariable=self.msg).pack(side="left", fill="x", expand=True, padx=10)
        self.btns = tk.Frame(f, bg=P["bg"])
        self.btns.pack(fill="x", pady=(12, 0))
        self.refresh()

    def _show(self, text):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        for line in text.split("\n"):
            tag = "add" if line.startswith("+") and not line.startswith("+++") else \
                  "del" if line.startswith("-") and not line.startswith("---") else ""
            self.out.insert("end", line + "\n", tag)
        self.out.config(state="disabled")

    def _buttons(self, items):
        for w in self.btns.winfo_children():
            w.destroy()
        for text, cmd, accent in items:
            Pill(self.btns, text, cmd, width=150, height=36, size=9, bg=P["accent"] if accent else None,
                 hover=P["accent_hi"] if accent else None, fg="white" if accent else None).pack(side="left", padx=(0, 8))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if not gitutil.have_git():
            self.head.config(text="Git o'rnatilmagan")
            self.sub.config(text="git-scm.com saytidan Git ni o'rnating, so'ng bu oynani qayta oching.")
            return self._buttons([])
        if not gitutil.is_repo(self.root_dir):
            self.head.config(text="Bu papka hali Git omboriga aylanmagan")
            self.sub.config(text="Git o'zgarishlaringiz tarixini saqlaydi. Boshlash uchun tugmani bosing.")
            return self._buttons([("Git omborini yaratish", self.init, True)])
        rows = gitutil.status(self.root_dir)
        self.head.config(text=f"Shox: {gitutil.branch(self.root_dir) or '—'}")
        self.sub.config(text=f"{len(rows)} ta fayl o'zgargan" if rows else "Hammasi saqlangan — o'zgarish yo'q")
        for w, path in rows:
            self.tree.insert("", "end", values=(w, path))
        d = gitutil.diff(self.root_dir) if rows else ""
        self._show(d if d != "(farq yo'q)" else ("Yangi fayllar «Saqlash» bosilganda qo'shiladi." if rows else ""))
        self._buttons([("Saqlash (commit)", self.commit, True), ("Yuborish (push)", lambda: self._net("push"), False),
                       ("Olish (pull)", lambda: self._net("pull"), False), ("Yangilash", self.refresh, False)])

    def init(self):
        ok, out = gitutil.run(self.root_dir, "init")
        self._show(out)
        self.refresh()

    def commit(self):
        text = self.msg.get().strip()
        if not text:
            return messagebox.showwarning("Diqqat", "Saqlash izohini yozing (nima o'zgardi?)", parent=self)
        ok, out = gitutil.commit_all(self.root_dir, text)
        self.msg.set("")
        self.refresh()
        self._show(("✓ Saqlandi\n\n" if ok else "Xato:\n") + out)

    def _net(self, what):
        self.config(cursor="watch")
        self.update()
        ok, out = gitutil.run(self.root_dir, what, timeout=120)
        self.config(cursor="")
        self.refresh()
        self._show(("✓ Bajarildi\n\n" if ok else "Xato:\n") + out)


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


class Chat:
    """Bitta suhbat: o'z tarixi, loyihasi, holati va ko'rinishi bor."""

    def __init__(self, inner, win, project):
        self.inner, self.win, self.project = inner, win, project
        self.orch = None
        self.title = "Yangi suhbat"
        self.busy = self.cancelled = self.unread = False
        self.typing = self.empty = self.dots = self.who = None
        self.pending: list = []


class TabButton(tk.Canvas):
    W, H = 190, 34

    def __init__(self, parent, chat, active, on_pick, on_close):
        super().__init__(parent, width=self.W, height=self.H, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.chat, self.active, self.on_pick, self.on_close, self.over = chat, active, on_pick, on_close, False
        self.bind("<Button-1>", self._click)
        self.bind("<Button-2>", lambda e: on_close(chat))
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.draw()

    def _h(self, v):
        self.over = v
        self.draw()

    def _click(self, e):
        (self.on_close if e.x > self.W - 28 else self.on_pick)(self.chat)

    def draw(self):
        self.delete("all")
        fill = P["card_hi"] if self.active else (P["card"] if self.over else P["side"])
        rrect(self, 0, 0, self.W, self.H, 12, fill=fill, outline=P["accent"] if self.active else "")
        c = self.chat
        if c.busy:
            self.create_oval(12, 13, 20, 21, fill=P["accent_hi"], outline="")
        elif c.unread:
            self.create_oval(12, 13, 20, 21, fill=P["ok"], outline="")
        title = c.title if len(c.title) <= 20 else c.title[:19] + "…"
        self.create_text(28, self.H / 2, text=title, anchor="w", font=font(9, "bold" if self.active else "normal"),
                         fill=P["text"] if self.active else P["muted"])
        self.create_text(self.W - 16, self.H / 2, text="×", fill=P["err"] if self.over else P["muted"], font=font(13))


def _delegate(name):
    return property(lambda s: getattr(s._a, name), lambda s, v: setattr(s._a, name, v))


class App(tk.Tk):
    PAD = 14
    orch, inner, busy, typing, empty = (_delegate(n) for n in ("orch", "inner", "busy", "typing", "empty"))
    cancelled, project, dots, who = (_delegate(n) for n in ("cancelled", "project", "dots", "who"))

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
        self.chats: list[Chat] = []
        self.cur: Chat | None = None
        self._override: Chat | None = None
        self._polling = False
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
        Pill(bottom, "＋  Yangi suhbat", lambda: self.new_chat(), bg=P["accent"], hover=P["accent_hi"], fg="white",
             height=42, radius=14).pack(fill="x", pady=(0, 8))
        Pill(bottom, "⚙   Sozlamalar", self.open_settings, bg=P["card"], hover=P["card_hi"],
             height=42, radius=14).pack(fill="x")
        self.agent_box = tk.Frame(inner, bg=P["side"])
        self.agent_box.pack(fill="both", expand=True)

    def _build_main(self):
        main = tk.Frame(self, bg=P["bg"])
        main.pack(side="right", fill="both", expand=True)

        self.tabbar = tk.Frame(main, bg=P["side"], padx=14, pady=8)
        self.tabbar.pack(fill="x")

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
        self.git_btn = Pill(head, "Git", self.open_git, width=64, height=34, size=9, outline=P["line"], bg=P["bg"])
        self.git_btn.pack(side="right", padx=(0, 8))
        self.clear_btn = Pill(head, "✕", self.clear_project, width=34, height=34, size=9, outline=P["line"], bg=P["bg"])
        self.proj_btn = Pill(head, "", self.choose_project, width=230, height=34, size=9, outline=P["line"], bg=P["bg"])
        self.proj_btn.pack(side="right", padx=(0, 8))
        tk.Frame(main, bg=P["line"], height=1).pack(fill="x")

        wrap = tk.Frame(main, bg=P["bg"])
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=P["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._canvas_resized)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel)

        self.chips = tk.Frame(main, bg=P["bg"])
        self.wrap = tk.Canvas(main, bg=P["bg"], height=72, highlightthickness=0)
        self.wrap.pack(fill="x", padx=28, pady=(8, 20))
        self.attach_btn = tk.Canvas(self.wrap, width=38, height=38, bg=P["card"], highlightthickness=0, cursor="hand2")
        self.attach_btn.bind("<Button-1>", lambda e: self.attach())
        self.attach_btn.bind("<Enter>", lambda e: self._attach_draw(True))
        self.attach_btn.bind("<Leave>", lambda e: self._attach_draw(False))
        self._attach_draw(False)
        self.entry = tk.Text(self.wrap, height=1, wrap="word", bg=P["card"], fg=P["text"], insertbackground=P["text"],
                             relief="flat", bd=0, highlightthickness=0, font=font(11), padx=2, pady=2)
        self.send_btn = tk.Canvas(self.wrap, width=44, height=44, bg=P["card"], highlightthickness=0, cursor="hand2")
        self.send_btn.bind("<Button-1>", lambda e: self.send())
        self.send_btn.bind("<Enter>", lambda e: self._send_draw(True))
        self.send_btn.bind("<Leave>", lambda e: self._send_draw(False))
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
    def _attach_draw(self, over):
        c = self.attach_btn
        c.delete("all")
        c.create_oval(2, 2, 36, 36, fill=P["accent"] if over else P["card_hi"], outline="")
        c.create_text(19, 18, text="+", fill="white", font=font(17, "bold"))

    def _send_draw(self, over):
        c = self.send_btn
        c.delete("all")
        busy = bool(self.cur and self.cur.busy)
        col = P["card_hi"] if busy else (P["accent_hi"] if over else P["accent"])
        c.create_oval(2, 2, 42, 42, fill=P["err"] if busy and over else col, outline="")
        if busy:
            c.create_rectangle(15, 15, 29, 29, fill="white", outline="")
        else:
            c.create_text(22, 22, text="↑", fill="white", font=font(17, "bold"))

    def _layout_input(self):
        w, h = self.wrap.winfo_width(), self.wrap.winfo_height()
        self.wrap.delete("all")
        rrect(self.wrap, 1, 1, w - 1, h - 1, 26, fill=P["card"], outline=P["line"])
        self.wrap.create_window(30, h / 2, window=self.attach_btn)
        self.wrap.create_window(56, h / 2, window=self.entry, anchor="w", width=max(50, w - 140), height=h - 26)
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
        note = "  ·  loyihada faqat o'qiydi" if self.project and key in READ_ONLY_MODES else ""
        self.sub_lbl.config(text=desc + note)

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

    @property
    def _a(self) -> Chat:
        return self._override or self.cur

    @contextlib.contextmanager
    def _as(self, chat):
        prev, self._override = self._override, chat
        try:
            yield
        finally:
            self._override = prev

    def _make_orch(self, chat):
        o = config.build(self.cfg)
        o.ctx.confirm = lambda agent, kind, title, detail, c=chat: self._confirm_threadsafe(c, agent, kind, title, detail)
        o.ctx.emit = lambda agent, kind, text, c=chat: self.inbox.put(("event", c, agent, kind, text))
        o.ctx.root = chat.project or None
        o.ctx.web = bool(self.cfg.get("web", True))
        return o

    def rebuild(self):
        """Agentlar yoki sozlamalar o'zgarganda: suhbatlar tarixi saqlanadi."""
        if not self.chats:
            self.new_chat()
        for c in self.chats:
            hist = c.orch.history
            c.orch = self._make_orch(c)
            c.orch.history = hist
            if c.empty is not None:
                with self._as(c):
                    self.empty.destroy()
                    self._show_empty()
        self.selected = set(self.cur.orch.agents)
        for w in self.agent_box.winfo_children():
            w.destroy()
        for a in self.cur.orch.agents.values():
            AgentRow(self.agent_box, a, self.toggle_agent).pack(fill="x", pady=1)
        self.pick_mode(self.mode.get())
        self._count()

    # ---------- suhbatlar (tablar) ----------
    def new_chat(self):
        proj = self.cfg.get("project") or ""
        inner = tk.Frame(self.canvas, bg=P["bg"])
        win = self.canvas.create_window((0, 0), window=inner, anchor="nw", width=max(1, self.canvas.winfo_width()))
        chat = Chat(inner, win, proj if proj and Path(proj).is_dir() else "")
        inner.bind("<Configure>", lambda e: self._region() if self.cur is chat else None)
        chat.orch = self._make_orch(chat)
        self.chats.append(chat)
        with self._as(chat):
            self._show_empty()
        self.switch(chat)

    def switch(self, chat):
        self.cur = chat
        chat.unread = False
        for c in self.chats:
            self.canvas.itemconfigure(c.win, state="normal" if c is chat else "hidden")
        self.update_idletasks()
        self._region()
        self.canvas.yview_moveto(1)
        self._proj_label()
        self.pick_mode(self.mode.get())
        self._render_tabs()
        self._render_chips()
        self._send_draw(False)

    def close_chat(self, chat):
        if chat.busy:
            chat.cancelled = True
            chat.orch.ctx.cancel.set()
        idx = self.chats.index(chat)
        self.chats.remove(chat)
        self.canvas.delete(chat.win)
        chat.inner.destroy()
        if not self.chats:
            return self.new_chat()
        if self.cur is chat:
            self.switch(self.chats[min(idx, len(self.chats) - 1)])
        else:
            self._render_tabs()

    def _render_tabs(self):
        for w in self.tabbar.winfo_children():
            w.destroy()
        for c in self.chats:
            TabButton(self.tabbar, c, c is self.cur, self.switch, self.close_chat).pack(side="left", padx=(0, 6))
        Pill(self.tabbar, "+", lambda: self.new_chat(), width=38, height=34, size=13, bg=P["side"],
             hover=P["card"], fg=P["muted"]).pack(side="left")

    def _canvas_resized(self, e):
        for c in self.chats:
            self.canvas.itemconfig(c.win, width=e.width)
        self._region()

    def _region(self):
        if self.cur:
            h = max(self.cur.inner.winfo_reqheight(), self.canvas.winfo_height())
            self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), h))

    # ---------- biriktirmalar ----------
    def attach(self):
        paths = filedialog.askopenfilenames(parent=self, title="Fayl biriktirish (rasm, PDF, Word, matn)",
                                            filetypes=attachments.FILETYPES)
        for p in paths:
            try:
                self.cur.pending.append(attachments.load(p))
            except attachments.AttachError as exc:
                messagebox.showwarning("Fayl biriktirilmadi", str(exc), parent=self)
        self._render_chips()
        self.entry.focus_set()

    def _remove_attachment(self, a):
        self.cur.pending.remove(a)
        self._render_chips()

    def _render_chips(self):
        for w in self.chips.winfo_children():
            w.destroy()
        if not self.cur or not self.cur.pending:
            return self.chips.pack_forget()
        self.chips.pack(fill="x", padx=28, before=self.wrap)
        for a in self.cur.pending:
            f = tk.Frame(self.chips, bg=P["card_hi"], padx=10, pady=4)
            f.pack(side="left", padx=(0, 8))
            label(f, ("▣ " if a.kind == "image" else "▤ ") + a.name, size=9).pack(side="left")
            x = label(f, "  ✕", fg=P["muted"], size=9, cursor="hand2")
            x.pack(side="left")
            x.bind("<Button-1>", lambda e, a=a: self._remove_attachment(a))

    # ---------- loyiha va git ----------
    def _proj_label(self):
        if self.project:
            name = Path(self.project).name or self.project
            self.proj_btn.set_text("Loyiha:  " + (name if len(name) < 22 else name[:20] + "…"))
            if not self.clear_btn.winfo_ismapped():
                self.clear_btn.pack(side="right", padx=(0, 8), before=self.proj_btn)
        else:
            self.proj_btn.set_text("Loyiha papkasini tanlash")
            self.clear_btn.pack_forget()

    def choose_project(self):
        d = filedialog.askdirectory(parent=self, title="Loyiha papkasini tanlang", initialdir=self.project or str(Path.home()))
        if d:
            self.set_project(str(Path(d)))

    def clear_project(self):
        self.set_project("")

    def set_project(self, path):
        self.project = path
        self.cfg["project"] = path  # yangi suhbatlar shu papka bilan boshlanadi
        config.write(self.cfg, self.cfg_path)
        self.orch.ctx.root = path or None
        self.orch.ctx.always.clear()
        self._proj_label()
        self.pick_mode(self.mode.get())
        if self.empty is not None:
            self.empty.destroy()
            self._show_empty()

    def open_git(self):
        if not self.project:
            return messagebox.showinfo("Git", "Avval «Loyiha papkasini tanlash» tugmasi bilan papkani tanlang.", parent=self)
        GitDialog(self, self.project)

    def _confirm_threadsafe(self, chat, agent, kind, title, detail):
        evt, box = threading.Event(), ["no"]
        self.inbox.put(("ask", chat, agent, kind, title, detail, box, evt))
        evt.wait(timeout=900)
        return box[0]

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
              (f"Loyiha: {self.project}\nAgentlar fayllarni o'qiydi va ruxsatingiz bilan o'zgartiradi." if self.project else
               "Savolingizni yozing — agentlaringiz birgalikda javob beradi."), fg=P["muted"], size=11).pack()
        chips = tk.Frame(box, bg=P["bg"])
        chips.pack(pady=26)
        for i, s in enumerate(PROJECT_SUGGESTIONS if self.project else SUGGESTIONS):
            Pill(chips, s, lambda s=s: self._use_suggestion(s), width=290, height=44, radius=16, size=10,
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

    def add_user(self, text, files=()):
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        col = tk.Frame(row, bg=P["bg"])
        col.pack(side="right")
        if files:
            label(col, "   ".join(("▣ " if a.kind == "image" else "▤ ") + a.name for a in files), fg=P["muted"],
                  size=9).pack(anchor="e", pady=(0, 4))
        self._bubble(col, text, P["user"], "white").pack(anchor="e")
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

    def add_activity(self, agent, kind, text):
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=1)
        label(row, f"{KIND_ICON.get(kind, '•')}  {agent}: {text}", fg=KIND_COLOR.get(kind, P["muted"]), size=9,
              wraplength=700, justify="left").pack(side="left", padx=(46, 0))
        if self.typing is not None:
            self.typing.pack_forget()
            self.typing.pack(fill="x", padx=28, pady=8)
        self._scroll()

    def _scroll(self):
        if self._a is not self.cur:
            return
        self.update_idletasks()
        self._region()
        self.canvas.yview_moveto(1)
        self.after(150, lambda: (self._region(), self.canvas.yview_moveto(1)))  # pufakcha aniq o'lchamga kelgach

    def _typing_on(self, names):
        chat = self._a
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        chat.dots = label(row, "", fg=P["accent_hi"], size=14, weight="bold")
        chat.dots.pack(side="left", padx=(46, 0))
        chat.who = label(row, "  " + ", ".join(names) + " yozmoqda…", fg=P["muted"], size=9)
        chat.who.pack(side="left")
        chat.typing = row
        self._tick(chat, 0)
        self._scroll()

    def _tick(self, chat, i):
        if chat.typing is None or chat not in self.chats:
            return
        chat.dots.config(text=["●○○", "○●○", "○○●"][i % 3])
        self.after(280, self._tick, chat, i + 1)

    def stop(self):
        self.cancelled = True
        self.orch.ctx.cancel.set()
        if self.typing is not None:
            self.who.config(text="  To'xtatilmoqda…")

    def send(self):
        if self.busy:
            return self.stop()
        chat = self.cur
        prompt, files = self._text(), list(chat.pending)
        if not prompt and not files:
            return
        prompt = prompt or "Biriktirilgan fayl(lar)ni ko'rib chiq va qisqacha tushuntir."
        self.entry.delete("1.0", "end")
        self._grow()
        if chat.title == "Yangi suhbat":
            chat.title = prompt.replace("\n", " ")[:22]
        self.add_user(prompt, files)
        chat.pending = []
        self._render_chips()
        mode = self.mode.get()
        targets = [n for n in self.orch.agents if n in self.selected]
        shown = targets[:1] if mode == "single" else targets
        self.busy, self.cancelled = True, False
        self._send_draw(False)
        self._render_tabs()
        self._typing_on(shown)
        if not self._polling:
            self._polling = True
            self.after(100, self._poll)
        threading.Thread(target=self._work, args=(chat, prompt, mode, targets, files), daemon=True).start()

    def _work(self, chat, prompt, mode, targets, files):
        try:
            res, err = chat.orch.run(prompt, mode, targets, files), ""
        except Exception as exc:
            res, err = [], str(exc)
        self.inbox.put(("done", chat, res, err))

    def _poll(self):
        while True:
            try:
                item = self.inbox.get_nowait()
            except queue.Empty:
                break
            chat = item[1]
            if chat not in self.chats:  # suhbat yopilgan
                if item[0] == "ask":
                    item[-2][0] = "no"
                    item[-1].set()
                continue
            with self._as(chat):
                if item[0] == "event":
                    self.add_activity(*item[2:])
                elif item[0] == "ask":
                    _, _, agent, kind, title, detail, box, evt = item
                    if chat.cancelled:
                        box[0] = "no"
                    else:
                        d = ApproveDialog(self, f"{agent} · {chat.title}", kind, title, detail)
                        self.wait_window(d)
                        box[0] = d.result
                    evt.set()
                else:
                    self._done(item[2], item[3])
        if any(c.busy for c in self.chats):
            self.after(100, self._poll)
        else:
            self._polling = False

    def _done(self, results, error):
        chat = self._a
        if self.typing is not None:
            self.typing.destroy()
            self.typing = None
        if self.cancelled:
            self.add_activity("Siz", "info", "Ish to'xtatildi.")
            results = []
        if error:
            self.add_agent("Xato", error, err=True)
        for r in results:
            if r.ok:
                self.add_agent(r.agent, r.text or "(bo'sh javob)", f"{r.seconds:.1f} s")
            else:
                self.add_agent(r.agent, r.error, "xato", err=True)
        chat.busy = False
        if chat is not self.cur:
            chat.unread = True
        else:
            self._send_draw(False)
            self.entry.focus_set()
        self._render_tabs()


def run(cfg_path: str | None = None):
    App(cfg_path).mainloop()
