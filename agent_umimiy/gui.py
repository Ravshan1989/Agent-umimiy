from __future__ import annotations

import contextlib
import copy
import itertools
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import attachments, chatstore, config, detect, gitutil, i18n, markdown, theme
from . import mcp as mcplib
from . import remote as remotelib
from . import server as serverlib
from . import skills as skilllib
from .orchestrator import READ_ONLY_MODES
from .providers import build_agent
from .theme import Avatar, P, Pill, color_for, font, label, rrect

MODES = {
    "auto": ("✦", "Avtomatik", "Eng mos agentni o'zi tanlaydi"),
    "single": ("◉", "Bitta agent", "Tanlangan birinchi agent javob beradi"),
    "broadcast": ("⇉", "Hammasi birga", "Barcha agentlar bir vaqtda javob beradi"),
    "pipeline": ("⇢", "Ketma-ket", "Har bir agent oldingisining javobini yaxshilaydi"),
    "consensus": ("⚖", "Kengash", "Hammasi javob beradi, hakam yagona xulosa chiqaradi"),
}
FREELLM_URL = "http://localhost:3001/v1"
TYPE_LABELS = {
    "freellm": "FreeLLMAPI — lokal shlyuz (localhost:3001)",
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
REAL_TYPE = {"freellm": "openai"}  # shablon -> haqiqiy agent turi
PROJECT_SUGGESTIONS = ["Bu loyiha nima haqida? Qisqa tushuntirib ber", "Kodda xatolarni top va tuzat",
                       "README.md faylini yoz yoki yangila", "Testlarni ishga tushir, xato bo'lsa tuzat"]
KIND_ICON = {"read": "◧", "write": "✎", "run": "▶", "info": "•", "agent": "⇄", "browser": "◎", "mcp": "⬡", "skill": "✧"}
KIND_COLOR = {"read": P["muted"], "write": P["warn"], "run": P["accent_hi"], "info": P["err"], "agent": P["ok"],
              "browser": P["accent_hi"], "mcp": P["accent_hi"], "skill": P["ok"]}
FILES_DIR = Path.home() / "Documents" / "Agent Umimiy"  # agent yaratgan Word/Excel fayllari
SUGGESTIONS = ["Bu kodni tushuntirib ber", "Menga qisqa xat yozib ber", "Ingliz tiliga tarjima qil",
               "Internetdan bugungi yangiliklarni top"]


def open_path(path) -> bool:
    """Fayl yoki papkani tizimning standart dasturida ochadi."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        return True
    except OSError:
        return False


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


def fit(win, w: int, h: int, center: bool = True):
    """Oynani ekran o'lchamiga moslaydi (noutbuk ekrani kichik bo'lsa ham to'liq ko'rinsin) va markazlaydi."""
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(w, sw - 40), min(h, sh - 110)  # vazifalar paneli va sarlavha uchun joy
    x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 2 - 20)
    win.geometry(f"{w}x{h}+{x}+{y}" if center else f"{w}x{h}")
    return w, h


def center(win):
    """O'lchami tarkibga qarab belgilanadigan oynani markazlaydi."""
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(win.winfo_reqwidth(), sw - 40), min(win.winfo_reqheight(), sh - 110)
    win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")


def scroll_body(win, pad=(22, 18)):
    """Oyna: tepada aylantiriladigan tarkib, pastda doim ko'rinadigan tugmalar paneli. (panel, tarkib) qaytaradi."""
    bar = tk.Frame(win, bg=P["bg"], padx=22, pady=10)
    bar.pack(side="bottom", fill="x")
    tk.Frame(win, bg=P["line"], height=1).pack(side="bottom", fill="x")
    wrap = tk.Frame(win, bg=P["bg"])
    wrap.pack(fill="both", expand=True)
    canvas = tk.Canvas(wrap, bg=P["bg"], highlightthickness=0)
    sb = ttk.Scrollbar(wrap, command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=P["bg"], padx=pad[0], pady=pad[1])
    wid = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

    def wheel(e):
        if canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(-3 if (e.num == 4 or e.delta > 0) else 3, "units")

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(seq, wheel)  # Toplevel barcha ichki vidjetlarning bindtags ida bor
    return bar, inner


class AgentDialog(tk.Toplevel):
    """Bitta agentni qo'shish/tahrirlash — JSON yozish shart emas."""

    def __init__(self, parent, spec=None):
        super().__init__(parent)
        self.title(i18n.t("Agent sozlamasi"))
        self.configure(bg=P["bg"])
        fit(self, 640, 600)
        self.result = None
        self.transient(parent)
        spec = spec or {}
        bar, f = scroll_body(self)
        label(f, i18n.t("Agent sozlamasi"), size=14, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.vars = {}
        rows = [("name", "Nomi"), ("type", "Turi"), ("model", "Model"), ("api_key", "API kalit"),
                ("base_url", "Manzil (ixtiyoriy)"), ("command", "Buyruq (CLI uchun)")]
        for i, (k, text) in enumerate(rows, start=1):
            label(f, i18n.t(text), fg=P["muted"]).grid(row=i, column=0, sticky="w", pady=5)
            v = tk.StringVar(value=spec.get(k, ""))
            if k == "type":
                v.set(i18n.t(TYPE_LABELS.get(spec.get("type", "anthropic"), TYPE_LABELS["anthropic"])))
                w = ttk.Combobox(f, textvariable=v, values=[i18n.t(x) for x in TYPE_LABELS.values()], state="readonly", width=38)
                w.bind("<<ComboboxSelected>>", lambda e: self._type_changed())
            elif k == "model":
                w = ttk.Combobox(f, textvariable=v, values=[], width=38)
                self.model_box = w
                Pill(f, i18n.t("Ro'yxat"), self._load_models, width=70, height=30, size=9, outline=P["line"],
                     bg=P["bg"]).grid(row=i, column=2, padx=(8, 0))
            else:
                w = ttk.Entry(f, textvariable=v, width=40, show="•" if k == "api_key" else "")
            w.grid(row=i, column=1, pady=5, padx=(12, 0))
            self.vars[k] = v
        self.hint = label(f, "", fg=P["muted"], size=9, wraplength=380, justify="left")
        self.hint.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(8, 12))
        self._hint()
        btns = tk.Frame(bar, bg=P["bg"])
        btns.pack(anchor="e")
        Pill(btns, i18n.t("Bekor"), self.destroy, width=90).pack(side="left", padx=4)
        Pill(btns, i18n.t("Sinab ko'rish"), self._test, width=130, outline=P["line"], bg=P["bg"]).pack(side="left", padx=4)
        Pill(btns, i18n.t("Saqlash"), self._save, width=110, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(side="left")
        self.grab_set()

    def _type(self):
        lbl = self.vars["type"].get()
        for k, v in TYPE_LABELS.items():
            if lbl in (v, i18n.t(v)):
                return k
        return "anthropic"

    def _type_changed(self):
        if self._type() == "freellm":
            self.vars["base_url"].set(FREELLM_URL)
            if not self.vars["name"].get():
                self.vars["name"].set("freellmapi")
        self._hint()

    def _load_models(self):
        t = REAL_TYPE.get(self._type(), self._type())
        url = self.vars["base_url"].get().strip() or ("https://api.openai.com/v1" if t == "openai" else "")
        if t != "openai" or not url:
            return messagebox.showinfo(i18n.t("Modellar ro'yxati"), i18n.t("Ro'yxat OpenAI-mos shlyuzlar (FreeLLMAPI, LM Studio, OpenRouter...) uchun ishlaydi. Boshqalarda model nomini o'zingiz yozing."), parent=self)
        self.config(cursor="watch")
        self.update()
        try:
            ids = detect.list_models(url, self.vars["api_key"].get().strip())
        except Exception as exc:
            self.config(cursor="")
            return messagebox.showerror(i18n.t("Ro'yxat olinmadi"), f"{exc}\n\n" + i18n.t("Shlyuz ishlayotganini va API kalit to'g'riligini tekshiring."), parent=self)
        self.config(cursor="")
        self.model_box["values"] = ids
        if ids and not self.vars["model"].get():
            self.vars["model"].set(ids[0])
        messagebox.showinfo(i18n.t("Modellar ro'yxati"), f"{len(ids)} " + i18n.t("ta model topildi. Ro'yxatdan tanlang."), parent=self)

    def _hint(self):
        self.hint.config(text=i18n.t({
            "freellm": "Brauzerda localhost:3001 → «Agentlar» bo'limidagi API KEY ni «API kalit» maydoniga qo'ying, so'ng «Ro'yxat» tugmasi bilan modelni tanlang.",
            "anthropic": "Kalitni console.anthropic.com dan oling. Model bo'sh qolsa, standarti ishlatiladi.",
            "openai": "OpenAI, OpenRouter, Groq yoki LM Studio. Lokal bo'lsa manzilni yozing: http://localhost:1234/v1",
            "gemini": "Kalitni aistudio.google.com dan oling.",
            "ollama": "Avval ollama.com dan o'rnating va modelni yuklab oling. Kalit shart emas.",
            "cli": "Masalan: codex exec {prompt}  yoki  claude -p {prompt}",
        }[self._type()]))

    def _spec(self):
        t = REAL_TYPE.get(self._type(), self._type())
        s = {"name": self.vars["name"].get().strip(), "type": t}
        for k in ("model", "api_key", "base_url", "command"):
            val = self.vars[k].get().strip()
            if val:
                s[k] = val
        if "model" not in s and t in DEFAULT_MODEL and self._type() != "freellm":
            s["model"] = DEFAULT_MODEL[t]
        return s

    def _test(self):
        s = self._spec()
        if not s["name"]:
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Nomini yozing"), parent=self)
        if self._type() == "freellm" and not self.vars["model"].get().strip():
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Avval «Ro'yxat» tugmasi bilan modelni tanlang."), parent=self)
        self.config(cursor="watch")
        self.update()
        r = build_agent(s).ask("Salom! Bir so'z bilan javob ber.")
        self.config(cursor="")
        if r.ok:
            messagebox.showinfo(i18n.t("Ishlayapti ✓"), r.text[:300], parent=self)
        else:
            messagebox.showerror(i18n.t("Xato"), r.error, parent=self)

    def _save(self):
        s = self._spec()
        if not s["name"]:
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Nomini yozing"), parent=self)
        if self._type() == "freellm" and not self.vars["model"].get().strip():
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Avval «Ro'yxat» tugmasi bilan modelni tanlang."), parent=self)
        if s["type"] == "cli" and not s.get("command"):
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Buyruqni yozing"), parent=self)
        self.result = s
        self.destroy()


class Settings(tk.Toplevel):
    def __init__(self, parent, cfg, on_save):
        super().__init__(parent)
        self.title(i18n.t("Sozlamalar"))
        self.configure(bg=P["bg"])
        self.cfg, self.on_save = cfg, on_save
        fit(self, 720, 760)
        self.transient(parent)
        bar, f = scroll_body(self)
        label(f, i18n.t("Agentlaringiz"), size=15, weight="bold").pack(anchor="w")
        label(f, i18n.t("Qo'shing, tahrirlang yoki vaqtincha o'chirib qo'ying"), fg=P["muted"], size=9).pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(f, columns=("type", "model", "on"), show="headings", height=8)
        for c, t, w in (("type", "Agent", 250), ("model", "Model / buyruq", 220), ("on", "Yoqilgan", 80)):
            self.tree.heading(c, text=i18n.t(t))
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True)
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=12)
        for text, cmd, w in (("+ Qo'shish", self.add, 100), ("Tahrirlash", self.edit, 100), ("O'chirish", self.remove, 90),
                             ("Yoq / o'chir", self.toggle, 110), ("Avto-topish", self.autodetect, 110)):
            Pill(row, i18n.t(text), cmd, width=w, height=34, size=9).pack(side="left", padx=(0, 6))
        jr = tk.Frame(f, bg=P["bg"])
        jr.pack(fill="x")
        label(jr, i18n.t("Kengashda hakam:"), fg=P["muted"]).pack(side="left")
        self.judge = tk.StringVar(value=cfg.get("judge", ""))
        self.judge_box = ttk.Combobox(jr, textvariable=self.judge, state="readonly", width=24)
        self.judge_box.pack(side="left", padx=10)
        lr = tk.Frame(f, bg=P["bg"])
        lr.pack(fill="x", pady=(12, 0))
        label(lr, i18n.t("Interfeys tili") + ":", fg=P["muted"]).pack(side="left")
        self._lang_names = {i18n.LANG_NAMES[c]: c for c in i18n.LANGS}
        self.lang = tk.StringVar(value=i18n.LANG_NAMES.get(cfg.get("lang", "uz"), i18n.LANG_NAMES["uz"]))
        ttk.Combobox(lr, textvariable=self.lang, state="readonly", width=16,
                     values=list(self._lang_names)).pack(side="left", padx=10)
        tr = tk.Frame(f, bg=P["bg"])
        tr.pack(fill="x", pady=(10, 0))
        label(tr, i18n.t("Mavzu") + ":", fg=P["muted"]).pack(side="left")
        self._theme_names = {i18n.t("Qorong'i"): "dark", i18n.t("Yorug'"): "light"}
        self.theme_var = tk.StringVar(value=next((k for k, v in self._theme_names.items()
                                                   if v == cfg.get("theme", "dark")), i18n.t("Qorong'i")))
        ttk.Combobox(tr, textvariable=self.theme_var, state="readonly", width=14,
                     values=list(self._theme_names)).pack(side="left", padx=10)
        label(tr, i18n.t("Urg'u rang") + ":", fg=P["muted"]).pack(side="left", padx=(12, 0))
        self.accent_var = tk.StringVar(value=cfg.get("accent", "violet"))
        ttk.Combobox(tr, textvariable=self.accent_var, state="readonly", width=12,
                     values=list(theme.ACCENTS)).pack(side="left", padx=10)
        label(f, i18n.t("Til, mavzu va rang o'zgarishi dasturni qayta ishga tushirgandan so'ng qo'llanadi."),
              fg=P["muted"], size=8).pack(anchor="w", pady=(4, 0))
        self.keep = tk.BooleanVar(value=cfg.get("save_chats", True))
        tk.Checkbutton(f, text=i18n.t("Suhbatlarni shu kompyuterda saqlash (dastur qayta ochilganda tiklanadi)"), variable=self.keep,
                       bg=P["bg"], fg=P["text"], selectcolor=P["card"], activebackground=P["bg"],
                       activeforeground=P["text"], highlightthickness=0, bd=0, font=font(10)).pack(anchor="w", pady=(12, 0))
        Pill(f, i18n.t("Suhbatlar tarixini o'chirish"), self._wipe, width=210, height=32, size=9, fg=P["err"],
             outline=P["line"], bg=P["bg"]).pack(anchor="w", pady=(8, 0))
        self.brow = tk.BooleanVar(value=cfg.get("browser", True))
        tk.Checkbutton(f, text=i18n.t("Agentlar brauzerni boshqara olsin (sayt ochish, bosish, yozish — har safar ruxsat so'raydi)"),
                       variable=self.brow, bg=P["bg"], fg=P["text"], selectcolor=P["card"], activebackground=P["bg"],
                       activeforeground=P["text"], highlightthickness=0, bd=0, font=font(10)).pack(anchor="w", pady=(12, 0))
        Pill(f, i18n.t("Telefondan boshqarish (mobil kirish)…"), lambda: self.master.open_remote(), width=300, height=32, size=9,
             outline=P["line"], bg=P["bg"]).pack(anchor="w", pady=(8, 0))
        Pill(f, i18n.t("Veb-server (boshqalar brauzerdan ishlatadi)…"), lambda: self.master.open_server(), width=300, height=32,
             size=9, outline=P["line"], bg=P["bg"]).pack(anchor="w", pady=(8, 0))
        self.web = tk.BooleanVar(value=cfg.get("web", True))
        tk.Checkbutton(f, text=i18n.t("Agentlar internetdan qidira va sahifalarni o'qiy olsin"), variable=self.web, bg=P["bg"],
                       fg=P["text"], selectcolor=P["card"], activebackground=P["bg"], activeforeground=P["text"],
                       highlightthickness=0, bd=0, font=font(10)).pack(anchor="w", pady=(12, 0))
        Pill(bar, i18n.t("Saqlash va yopish"), self.save, width=170, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(anchor="e")
        self.refresh()

    def _wipe(self):
        if messagebox.askyesno(i18n.t("Tarixni o'chirish"), i18n.t("Barcha saqlangan suhbatlar o'chirilsinmi?"), parent=self):
            self.master.clear_history()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self.cfg["agents"]):
            self.tree.insert("", "end", iid=str(i), values=(
                f"{a['name']}  ·  {i18n.t(SHORT_TYPE.get(a['type'], a['type']))}",
                a.get("model") or a.get("command", ""), i18n.t("ha") if a.get("enabled", True) else i18n.t("yo'q")))
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
        if i is not None and messagebox.askyesno(i18n.t("O'chirish"), i18n.t("Bu agent o'chirilsinmi?"), parent=self):
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
        messagebox.showinfo(i18n.t("Avto-topish"), f"{len(new)} " + i18n.t("ta yangi agent topildi.") if new else
                            i18n.t("Yangi agent topilmadi. Ollama/LM Studio ishga tushirilganini tekshiring."), parent=self)

    def save(self):
        self.cfg["judge"] = self.judge.get()
        self.cfg["web"] = bool(self.web.get())
        self.cfg["browser"] = bool(self.brow.get())
        self.cfg["save_chats"] = bool(self.keep.get())
        self.cfg["lang"] = self._lang_names.get(self.lang.get(), "uz")
        self.cfg["theme"] = self._theme_names.get(self.theme_var.get(), "dark")
        self.cfg["accent"] = self.accent_var.get() if self.accent_var.get() in theme.ACCENTS else "violet"
        i18n.set_lang(self.cfg["lang"])
        self.on_save(self.cfg)
        self.destroy()


class ApproveDialog(tk.Toplevel):
    """Agent fayl o'zgartirmoqchi yoki buyruq ishga tushirmoqchi bo'lganda ruxsat so'raydi."""

    def __init__(self, parent, agent, kind, title, detail):
        super().__init__(parent)
        self.title(i18n.t("Ruxsat kerak"))
        self.configure(bg=P["bg"])
        self.transient(parent)
        self.result = "no"
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack(fill="both", expand=True)
        label(f, f"{agent} " + i18n.t("ruxsat so'ramoqda"), fg=P["warn"], size=9, weight="bold").pack(anchor="w")
        label(f, title, size=13, weight="bold", wraplength=560, justify="left").pack(anchor="w", pady=(2, 10))
        box = tk.Text(f, width=76, height=14, bg=P["code"], fg="#c9d1ff", relief="flat", bd=0, font=font(10, mono=True),
                      padx=10, pady=8, wrap="none" if kind == "write" else "word", highlightthickness=0)
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
        always = (i18n.t("Shu suhbatda doim ruxsat") if kind == "write" else
                  i18n.t("Brauzerda doim ruxsat") if kind.startswith("browser") else
                  i18n.t("Bu plaginga doim ruxsat") if kind.startswith("mcp") else i18n.t("Buyruqlarga doim ruxsat"))
        Pill(row, i18n.t("Rad etish"), lambda: self._done("no"), width=110, fg=P["err"]).pack(side="left")
        Pill(row, i18n.t("Ruxsat berish"), lambda: self._done("yes"), width=140, bg=P["accent"], hover=P["accent_hi"],
             fg="white").pack(side="right")
        Pill(row, always, lambda: self._done("always"), width=190, outline=P["line"], bg=P["bg"]).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", lambda: self._done("no"))
        center(self)
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
        self.title(i18n.t("Git — o'zgarishlar"))
        self.configure(bg=P["bg"])
        fit(self, 760, 640)
        self.transient(parent)
        f = tk.Frame(self, bg=P["bg"], padx=22, pady=18)
        f.pack(fill="both", expand=True)
        self.head = label(f, "", size=14, weight="bold")
        self.head.pack(anchor="w")
        self.sub = label(f, "", fg=P["muted"], size=9)
        self.sub.pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(f, columns=("what", "file"), show="headings", height=6)
        self.tree.heading("what", text=i18n.t("Holati"))
        self.tree.heading("file", text=i18n.t("Fayl"))
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
        label(msg, i18n.t("Saqlash izohi:"), fg=P["muted"]).pack(side="left")
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
            self.head.config(text=i18n.t("Git o'rnatilmagan"))
            self.sub.config(text=i18n.t("git-scm.com saytidan Git ni o'rnating, so'ng bu oynani qayta oching."))
            return self._buttons([])
        if not gitutil.is_repo(self.root_dir):
            self.head.config(text=i18n.t("Bu papka hali Git omboriga aylanmagan"))
            self.sub.config(text=i18n.t("Git o'zgarishlaringiz tarixini saqlaydi. Boshlash uchun tugmani bosing."))
            return self._buttons([(i18n.t("Git omborini yaratish"), self.init, True)])
        rows = gitutil.status(self.root_dir)
        self.head.config(text=i18n.t("Shox:") + f" {gitutil.branch(self.root_dir) or '—'}")
        self.sub.config(text=f"{len(rows)} " + i18n.t("ta fayl o'zgargan") if rows else i18n.t("Hammasi saqlangan — o'zgarish yo'q"))
        for w, path in rows:
            self.tree.insert("", "end", values=(w, path))
        d = gitutil.diff(self.root_dir) if rows else ""
        self._show(d if d != "(farq yo'q)" else (i18n.t("Yangi fayllar «Saqlash» bosilganda qo'shiladi.") if rows else ""))
        self._buttons([(i18n.t("Saqlash (commit)"), self.commit, True), (i18n.t("Yuborish (push)"), lambda: self._net("push"), False),
                       (i18n.t("Olish (pull)"), lambda: self._net("pull"), False), (i18n.t("Yangilash"), self.refresh, False)])

    def init(self):
        ok, out = gitutil.run(self.root_dir, "init")
        self._show(out)
        self.refresh()

    def commit(self):
        text = self.msg.get().strip()
        if not text:
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Saqlash izohini yozing (nima o'zgardi?)"), parent=self)
        ok, out = gitutil.commit_all(self.root_dir, text)
        self.msg.set("")
        self.refresh()
        self._show((i18n.t("✓ Saqlandi") + "\n\n" if ok else i18n.t("Xato:") + "\n") + out)

    def _net(self, what):
        self.config(cursor="watch")
        self.update()
        ok, out = gitutil.run(self.root_dir, what, timeout=120)
        self.config(cursor="")
        self.refresh()
        self._show((i18n.t("✓ Bajarildi") + "\n\n" if ok else i18n.t("Xato:") + "\n") + out)


class RemoteDialog(tk.Toplevel):
    """Telefondan boshqarish: QR-kod, manzil, yoqish/o'chirish."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(i18n.t("Telefondan boshqarish"))
        self.configure(bg=P["bg"])
        fit(self, 600, 800)
        self.transient(app)
        bar, f = scroll_body(self, (24, 18))
        Pill(bar, i18n.t("Yopish"), self.destroy, width=100, height=34, size=9, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(anchor="e")
        label(f, i18n.t("Telefondan boshqarish"), size=15, weight="bold").pack(anchor="w")
        label(f, i18n.t("Telefon va kompyuter bir Wi-Fi tarmog'ida bo'lsin. QR-kodni telefon kamerasi bilan skanerlang: chat telefon brauzerida ochiladi, ruxsat so'rovlari ham telefonda chiqadi."), fg=P["muted"], size=9, wraplength=500, justify="left").pack(anchor="w", pady=(2, 10))
        self.status = label(f, "", size=11, weight="bold")
        self.status.pack(anchor="w")
        self.qr = tk.Canvas(f, width=230, height=230, bg="white", highlightthickness=0)
        self.qr.pack(pady=6)
        self.url_var = tk.StringVar()
        ipr = tk.Frame(f, bg=P["bg"])
        ipr.pack(fill="x", pady=(0, 6))
        label(ipr, i18n.t("Kompyuter manzili:"), fg=P["muted"], size=9).pack(side="left")
        self.ip_var = tk.StringVar()
        self.ip_box = ttk.Combobox(ipr, textvariable=self.ip_var, state="readonly", width=44)
        self.ip_box.pack(side="left", padx=8)
        self.ip_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Entry(f, textvariable=self.url_var, state="readonly").pack(fill="x")
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=10)
        self.toggle = Pill(row, "", self._toggle, width=130, height=34, size=9, bg=P["accent"], hover=P["accent_hi"], fg="white")
        self.toggle.pack(side="left", padx=(0, 6))
        Pill(row, i18n.t("Manzilni nusxalash"), self._copy, width=150, height=34, size=9).pack(side="left", padx=(0, 6))
        Pill(row, i18n.t("Yangi kalit"), self._renew, width=100, height=34, size=9).pack(side="left")
        fw = tk.Frame(f, bg=P["bg"])
        fw.pack(fill="x", pady=(0, 6))
        Pill(fw, i18n.t("Windows devoriga ruxsat berish"), self._firewall, width=230, height=34, size=9, outline=P["line"], bg=P["bg"]).pack(side="left")
        self.fw_lbl = label(fw, i18n.t("To'suvchi qoidalarni ham o'chiradi"), size=9, fg=P["muted"], wraplength=240, justify="left")
        self.fw_lbl.pack(side="left", padx=10)
        label(f, i18n.t("Ulanmasa, tekshiring:\n1) Telefonda mobil internet o'chiq, Wi-Fi yoqilgan va kompyuter bilan BIR XIL tarmoqda (mehmon/guest Wi-Fi emas).\n2) Yuqoridagi «Kompyuter manzili» ni boshqasiga almashtirib ko'ring (Docker/VPN bo'lsa, birinchisi noto'g'ri bo'lishi mumkin).\n3) «Windows devoriga ruxsat berish» tugmasini bosing (administrator so'raydi).\n4) Telefon brauzerida faqat manzilni oching (kalitsiz): http://MANZIL:PORT/ — sahifa ochilsa, tarmoq yaxshi.\n5) Kompyuter boshqa joyda (masalan, Chrome Remote Desktop orqali ulangan «SERVER») bo'lsa, telefon u bilan bir Wi-Fi'da bo'lmaydi: Tailscale ishlating."),
              fg=P["muted"], size=9, wraplength=500, justify="left").pack(anchor="w", pady=(0, 8))
        label(f, i18n.t("Xavfsizlik: manzildagi kalit (t=...) parol vazifasini bajaradi: uni hech kimga bermang. Ulanish shifrlanmagan (HTTP), shuning uchun faqat ishonchli uy Wi-Fi'ida ishlating. Boshqa joydan ulanish uchun Tailscale kabi shifrlangan tunnel o'rnating va shu manzildagi IP o'rniga kompyuterning Tailscale IP sini yozing. Kalit boshqaga ko'rinib qolsa, «Yangi kalit» ni bosing. Windows xavfsizlik devori so'rasa, «Ruxsat berish» (shaxsiy tarmoq) ni tanlang."),
              fg=P["muted"], size=9, wraplength=500, justify="left").pack(anchor="w", pady=(4, 0))
        self.refresh()

    def refresh(self):
        app = self.app
        on = app.remote is not None
        self.toggle.set_text(i18n.t("To'xtatish") if on else i18n.t("Yoqish"))
        self.qr.delete("all")
        if not on:
            self.status.config(text=i18n.t("○ O'chiq"), fg=P["muted"])
            self.url_var.set("")
            self.qr.create_text(115, 115, text=i18n.t("Yoqilmagan"), fill="#999", font=font(12))
            return
        ips = remotelib.local_ips()
        choices = [f"{o['ip']}  ({o['note']})" for o in ips] or [i18n.t("127.0.0.1  (faqat shu kompyuter)")]
        self.ip_box["values"] = choices
        if self.ip_var.get() not in choices:
            self.ip_var.set(choices[0])
        ip = self.ip_var.get().split()[0]
        url = app.remote.url(ip)
        ok, msg = app.remote.selftest(ip)
        self.status.config(text=(i18n.t("● Yoqilgan.") + " " + (i18n.t("Server kompyuterda ishlayapti.") if ok else i18n.t("Lekin server javob bermayapti!"))), fg=P["ok"] if ok else P["err"])
        self.url_var.set(url)
        try:
            import qrcode
            qr = qrcode.QRCode(border=4, box_size=1)
            qr.add_data(url)
            qr.make(fit=True)
            m = qr.get_matrix()
            cell = 230 // len(m)
            off = (230 - cell * len(m)) // 2
            for y, row in enumerate(m):
                for x, v in enumerate(row):
                    if v:
                        self.qr.create_rectangle(off + x * cell, off + y * cell, off + (x + 1) * cell, off + (y + 1) * cell,
                                                 fill="black", outline="black")
        except Exception:
            self.qr.create_text(115, 115, text=i18n.t("QR-kod yaratib bo'lmadi.\nManzilni qo'lda yozing."), fill="#555", font=font(11))

    def _firewall(self):
        if not self.app.remote:
            return messagebox.showinfo(i18n.t("Devor"), i18n.t("Avval «Yoqish» tugmasini bosing."), parent=self)
        ok, msg = remotelib.open_firewall(self.app.remote.port)
        self.fw_lbl.config(text=msg, fg=P["ok"] if ok else P["err"])
        if ok:
            self.after(4000, self._fw_check)

    def _fw_check(self):
        if not self.winfo_exists():
            return
        if remotelib.firewall_rule_exists():
            self.fw_lbl.config(text=i18n.t("✓ Qoida qo'shildi. Endi telefondan qayta urinib ko'ring."), fg=P["ok"])
        else:
            self.fw_lbl.config(text=i18n.t("Qoida topilmadi: administrator so'rovi rad etilgan yoki hali tugamagan."), fg=P["err"])

    def _toggle(self):
        if self.app.remote:
            self.app.stop_remote()
            self.app.cfg["remote"] = False
            config.write(self.app.cfg, self.app.cfg_path)
        else:
            self.app.start_remote()
        self.refresh()

    def _copy(self):
        if self.url_var.get():
            self.clipboard_clear()
            self.clipboard_append(self.url_var.get())

    def _renew(self):
        if messagebox.askyesno(i18n.t("Yangi kalit"), i18n.t("Eski manzil ishlamay qoladi, telefonda QR-kodni qayta skanerlash kerak. Davom etilsinmi?"), parent=self):
            self.app.new_remote_token()
            self.refresh()


class ServerDialog(tk.Toplevel):
    """Veb-server: yoqish/o'chirish, manzillar va taklif kodi."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title(i18n.t("Veb-server"))
        self.configure(bg=P["bg"])
        fit(self, 600, 620)
        self.transient(app)
        bar, f = scroll_body(self, (24, 18))
        Pill(bar, i18n.t("Yopish"), self.destroy, width=100, height=34, size=9, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(anchor="e")
        label(f, i18n.t("Veb-server"), size=15, weight="bold").pack(anchor="w")
        label(f, i18n.t("Lokal tarmoqdagi odamlar brauzerdan kirib, o'z suhbatlarida agentlaringizdan foydalanadi. Yoqilgan bo'lsa, dastur har ochilganda server o'zi ishga tushadi. Dastur yopilsa, server ham to'xtaydi."),
              fg=P["muted"], size=9, wraplength=500, justify="left").pack(anchor="w", pady=(2, 10))
        self.status = label(f, "", size=11, weight="bold")
        self.status.pack(anchor="w")
        label(f, i18n.t("Manzillar (odamlarga shulardan birini bering):"), fg=P["muted"], size=9).pack(anchor="w", pady=(10, 2))
        self.urls = tk.Text(f, height=4, wrap="none", bg=P["card"], fg=P["text"], relief="flat", bd=0, highlightthickness=0,
                            font=font(10, mono=True), padx=8, pady=6)
        self.urls.pack(fill="x")
        label(f, i18n.t("Taklif kodi (ro'yxatdan o'tish uchun):"), fg=P["muted"], size=9).pack(anchor="w", pady=(10, 2))
        self.invite_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.invite_var, state="readonly", font=font(14, mono=True)).pack(fill="x")
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=10)
        self.toggle = Pill(row, "", self._toggle, width=130, height=34, size=9, bg=P["accent"], hover=P["accent_hi"], fg="white")
        self.toggle.pack(side="left", padx=(0, 6))
        Pill(row, i18n.t("Yangi taklif kodi"), self._renew, width=150, height=34, size=9).pack(side="left", padx=(0, 6))
        Pill(row, i18n.t("Windows devoriga ruxsat berish"), self._firewall, width=230, height=34, size=9).pack(side="left")
        self.fw_lbl = label(f, "", size=9, fg=P["muted"], wraplength=500, justify="left")
        self.fw_lbl.pack(anchor="w")
        label(f, i18n.t("Hamma sizning API kalitlaringiz va limitingizdan foydalanadi. Veb-foydalanuvchilar uchun agentlar kompyuteringizdagi fayllarga, buyruqlarga, brauzerga va plaginlarga tegmaydi. Ulanish shifrlanmagan (HTTP): faqat ishonchli tarmoqda ishlating yoki Tailscale o'rnating."),
              fg=P["muted"], size=9, wraplength=500, justify="left").pack(anchor="w", pady=(8, 0))
        self.refresh()

    def refresh(self):
        httpd = self.app.web_server
        self.toggle.set_text(i18n.t("To'xtatish") if httpd else i18n.t("Yoqish"))
        self.status.config(text=i18n.t("● Yoqilgan.") if httpd else i18n.t("○ O'chiq"), fg=P["ok"] if httpd else P["muted"])
        self.urls.config(state="normal")
        self.urls.delete("1.0", "end")
        self.urls.insert("1.0", "\n".join(serverlib.urls(httpd)) if httpd else "")
        self.urls.config(state="disabled")
        self.invite_var.set(httpd.store.invite() if httpd else "")

    def _toggle(self):
        if self.app.web_server:
            self.app.stop_server()
            self.app.cfg["server"] = False
            config.write(self.app.cfg, self.app.cfg_path)
        else:
            self.app.start_server()
        self.refresh()

    def _renew(self):
        httpd = self.app.web_server
        if httpd and messagebox.askyesno(i18n.t("Yangi taklif kodi"), i18n.t("Eski kod ishlamay qoladi. Ro'yxatdan o'tib bo'lganlarga ta'sir qilmaydi. Davom etilsinmi?"), parent=self):
            httpd.store.new_invite()
            self.refresh()

    def _firewall(self):
        httpd = self.app.web_server
        if not httpd:
            return messagebox.showinfo(i18n.t("Devor"), i18n.t("Avval «Yoqish» tugmasini bosing."), parent=self)
        ok, msg = remotelib.open_firewall(httpd.server_port)
        self.fw_lbl.config(text=msg, fg=P["ok"] if ok else P["err"])


class McpDialog(tk.Toplevel):
    """Plagin (MCP server) qo'shish yoki tahrirlash."""

    TRANSPORTS = {"stdio": "Kompyuterdagi dastur (masalan npx ...)", "http": "Masofaviy server (URL)"}

    def __init__(self, parent, spec=None, taken=()):
        super().__init__(parent)
        self.title(i18n.t("Plagin sozlamasi"))
        self.configure(bg=P["bg"])
        fit(self, 700, 680)
        self.transient(parent)
        self.result, self.taken = None, set(taken)
        spec = spec or {}
        bar, f = scroll_body(self)
        label(f, i18n.t("Plagin sozlamasi"), size=14, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        r = 1
        if not spec:
            label(f, i18n.t("Shablon"), fg=P["muted"]).grid(row=r, column=0, sticky="w", pady=5)
            self.preset = tk.StringVar()
            cb = ttk.Combobox(f, textvariable=self.preset, values=[p["label"] for p in mcplib.PRESETS], state="readonly", width=44)
            cb.grid(row=r, column=1, pady=5, padx=(12, 0))
            cb.bind("<<ComboboxSelected>>", lambda e: self._apply_preset())
            r += 1
        self.v = {k: tk.StringVar(value=spec.get(k, "")) for k in ("name", "command", "url")}
        self.v["transport"] = tk.StringVar(value=i18n.t(self.TRANSPORTS.get(spec.get("transport", "stdio"))))
        for key, text in (("name", "Nomi (lotincha, probelsiz)"), ("transport", "Turi"), ("command", "Buyruq"), ("url", "URL")):
            label(f, i18n.t(text), fg=P["muted"]).grid(row=r, column=0, sticky="w", pady=5)
            if key == "transport":
                w = ttk.Combobox(f, textvariable=self.v[key], values=[i18n.t(x) for x in self.TRANSPORTS.values()], state="readonly", width=44)
            else:
                w = ttk.Entry(f, textvariable=self.v[key], width=47)
            w.grid(row=r, column=1, pady=5, padx=(12, 0))
            r += 1
        self.texts = {}
        for key, text in (("env", "Muhit o'zgaruvchilari\n(KALIT=qiymat, har qatorda bittadan)"), ("headers", "Sarlavhalar\n(Authorization: Bearer ..., har qatorda bittadan)")):
            label(f, i18n.t(text), fg=P["muted"], justify="left").grid(row=r, column=0, sticky="nw", pady=5)
            t = tk.Text(f, width=47, height=3, bg=P["card"], fg=P["text"], insertbackground=P["text"], relief="flat",
                        highlightthickness=1, highlightbackground=P["line"], font=font(10, mono=True))
            t.insert("1.0", spec.get(key, ""))
            t.grid(row=r, column=1, pady=5, padx=(12, 0))
            self.texts[key] = t
            r += 1
        self.note = label(f, i18n.t("Kalitlar faqat shu kompyuterdagi sozlama faylida saqlanadi."), fg=P["muted"], size=9, wraplength=480, justify="left")
        self.note.grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 12))
        btns = tk.Frame(bar, bg=P["bg"])
        btns.pack(anchor="e")
        Pill(btns, i18n.t("Bekor"), self.destroy, width=90).pack(side="left", padx=4)
        Pill(btns, i18n.t("Saqlash"), self._save, width=110, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(side="left")
        self.grab_set()

    def _apply_preset(self):
        p = next(x for x in mcplib.PRESETS if x["label"] == self.preset.get())
        self.v["name"].set(p["name"])
        self.v["transport"].set(i18n.t(self.TRANSPORTS[p["transport"]]))
        self.v["command"].set(p.get("command", ""))
        self.v["url"].set(p.get("url", ""))
        for k in ("env", "headers"):
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", p.get(k, ""))
        self.note.config(text=p["note"])

    def _save(self):
        name = re.sub(r"[^A-Za-z0-9_-]", "_", self.v["name"].get().strip())
        transport = next((k for k, t in self.TRANSPORTS.items() if self.v["transport"].get() in (t, i18n.t(t))), "stdio")
        if not name:
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Nomini yozing (lotin harflarida)"), parent=self)
        if name in self.taken:
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Bu nom band"), parent=self)
        if transport == "stdio" and not self.v["command"].get().strip():
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("Buyruqni yozing"), parent=self)
        if transport == "http" and not self.v["url"].get().strip():
            return messagebox.showwarning(i18n.t("Diqqat"), i18n.t("URL ni yozing"), parent=self)
        self.result = {"name": name, "transport": transport, "command": self.v["command"].get().strip(),
                       "url": self.v["url"].get().strip(), "env": self.texts["env"].get("1.0", "end").strip(),
                       "headers": self.texts["headers"].get("1.0", "end").strip()}
        self.destroy()


class PluginsDialog(tk.Toplevel):
    """Plaginlar (MCP serverlar) va ko'nikmalar (SKILL.md) boshqaruvi."""

    def __init__(self, parent, cfg, manager, on_save):
        super().__init__(parent)
        self.title(i18n.t("Plaginlar"))
        self.configure(bg=P["bg"])
        fit(self, 840, 800)
        self.transient(parent)
        self.cfg, self.manager, self.on_save = cfg, manager, on_save
        self.items: list = [dict(x) for x in cfg.get("mcp", [])]
        bar, f = scroll_body(self)
        Pill(bar, i18n.t("Yopish"), self.destroy, width=100, height=34, size=9, bg=P["accent"], hover=P["accent_hi"], fg="white").pack(anchor="e")
        label(f, i18n.t("Plaginlar"), size=15, weight="bold").pack(anchor="w")
        label(f, i18n.t("Tayyor xizmatlarni ulang: fayllar, Notion, GitHub, hujjatlar va boshqalar. Agentlar ularning asboblaridan foydalanadi."),
              fg=P["muted"], size=9, wraplength=760, justify="left").pack(anchor="w", pady=(0, 10))
        self.tree = ttk.Treeview(f, columns=("kind", "status", "tools"), show="tree headings", height=5)
        self.tree.heading("#0", text=i18n.t("Plagin"))
        self.tree.heading("kind", text=i18n.t("Turi"))
        self.tree.heading("status", text=i18n.t("Holati"))
        self.tree.heading("tools", text=i18n.t("Asboblar"))
        self.tree.column("#0", width=230)
        self.tree.column("kind", width=90)
        self.tree.column("status", width=280)
        self.tree.column("tools", width=80)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._detail())
        row = tk.Frame(f, bg=P["bg"])
        row.pack(fill="x", pady=10)
        for text, cmd, w in (("+ Qo'shish", self.add, 100), ("Tahrirlash", self.edit, 100), ("O'chirish", self.remove, 90),
                             ("Yoq / o'chir", self.toggle, 110), ("Qayta ulash", self.reconnect, 110)):
            Pill(row, i18n.t(text), cmd, width=w, height=34, size=9).pack(side="left", padx=(0, 6))
        self.detail = tk.Text(f, height=5, bg=P["code"], fg="#c9d1ff", relief="flat", bd=0, font=font(9, mono=True),
                              padx=10, pady=6, wrap="word", highlightthickness=0, state="disabled")
        self.detail.pack(fill="x")

        label(f, i18n.t("Ko'nikmalar (skills)"), size=13, weight="bold").pack(anchor="w", pady=(18, 0))
        label(f, i18n.t("Papkaga SKILL.md joylashtiring. Claude ko'nikmalari (~/.claude/skills) va loyihadagi .claude/skills avtomatik topiladi."),
              fg=P["muted"], size=9, wraplength=760, justify="left").pack(anchor="w", pady=(0, 8))
        self.skills = ttk.Treeview(f, columns=("src", "desc"), show="tree headings", height=5)
        self.skills.heading("#0", text=i18n.t("Ko'nikma"))
        self.skills.heading("src", text=i18n.t("Manba"))
        self.skills.heading("desc", text=i18n.t("Tavsif"))
        self.skills.column("#0", width=190)
        self.skills.column("src", width=110)
        self.skills.column("desc", width=420)
        self.skills.pack(fill="both", expand=True)
        row2 = tk.Frame(f, bg=P["bg"])
        row2.pack(fill="x", pady=(10, 0))
        Pill(row2, i18n.t("Ko'nikmalar papkasini ochish"), self.open_skills_dir, width=220, height=34, size=9).pack(side="left", padx=(0, 6))
        Pill(row2, i18n.t("Yangilash"), self._refresh_skills, width=100, height=34, size=9).pack(side="left")
        self._refresh_skills()
        self._tick()

    # -- MCP --
    def _status(self, item):
        if not item.get("enabled", True):
            return i18n.t("o'chiq"), 0, ""
        s = self.manager.servers.get(item["name"])
        if not s:
            return i18n.t("kutilmoqda"), 0, ""
        return s.status, len(s.tools), s.error

    def _tick(self):
        if not self.winfo_exists():
            return
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.items):
            st, n, _ = self._status(it)
            dot = {"tayyor": "● ", "xato": "✕ ", "ulanmoqda": "… "}.get(st, "○ ")
            self.tree.insert("", "end", iid=str(i), text=it["name"], values=(
                "HTTP" if it.get("transport") == "http" else i18n.t("dastur"), dot + i18n.t(st), n if st == "tayyor" else ""))
        if sel and sel[0] in self.tree.get_children():
            self.tree.selection_set(sel[0])
        self._detail()
        self.after(1000, self._tick)

    def _sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def _detail(self):
        i = self._sel()
        text = ""
        if i is not None and i < len(self.items):
            st, n, err = self._status(self.items[i])
            s = self.manager.servers.get(self.items[i]["name"])
            if err:
                text = i18n.t("Xato:") + " " + err
            elif s and s.tools:
                text = i18n.t("Asboblar:") + " " + ", ".join(t.get("name", "") for t in s.tools)
            elif st == "ulanmoqda":
                text = i18n.t("Ulanmoqda… (birinchi marta npx paketni yuklab oladi, 1-2 daqiqa ketishi mumkin)")
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    def _commit(self):
        self.on_save([dict(x) for x in self.items])

    def add(self):
        d = McpDialog(self, taken=[x["name"] for x in self.items])
        self.wait_window(d)
        if d.result:
            self.items.append(d.result)
            self._commit()

    def edit(self):
        i = self._sel()
        if i is None:
            return
        d = McpDialog(self, self.items[i], taken=[x["name"] for j, x in enumerate(self.items) if j != i])
        self.wait_window(d)
        if d.result:
            d.result["enabled"] = self.items[i].get("enabled", True)
            self.items[i] = d.result
            self._commit()

    def remove(self):
        i = self._sel()
        if i is not None and messagebox.askyesno(i18n.t("O'chirish"), i18n.t("Bu plagin o'chirilsinmi?"), parent=self):
            del self.items[i]
            self._commit()

    def toggle(self):
        i = self._sel()
        if i is not None:
            self.items[i]["enabled"] = not self.items[i].get("enabled", True)
            self._commit()

    def reconnect(self):
        i = self._sel()
        if i is not None:
            self.manager.reconnect(self.items[i]["name"])

    # -- ko'nikmalar --
    def _refresh_skills(self):
        skilllib._cache.clear()
        self.skills.delete(*self.skills.get_children())
        proj = getattr(self.master, "project", None) or None
        for s in skilllib.discover(proj, ttl=0):
            self.skills.insert("", "end", text=s.name, values=(s.source, s.description))

    def open_skills_dir(self):
        d = config.user_dir() / "skills"
        d.mkdir(parents=True, exist_ok=True)
        if not open_path(d):
            messagebox.showinfo(i18n.t("Papka"), str(d), parent=self)


class ModeRow(tk.Canvas):
    def __init__(self, parent, key, on_pick, height=40):
        super().__init__(parent, height=height, bg=P["side"], highlightthickness=0, cursor="hand2")
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
            rrect(self, 0, 0, w, h, 14, fill=P["card_hi"], outline=P["accent"])
        elif self.over:
            rrect(self, 0, 0, w, h, 14, fill=P["card"], outline="")
        self.create_text(22, h / 2, text=icon, fill=P["accent_hi"] if self.active else P["muted"], font=font(13))
        self.create_text(46, h / 2, text=i18n.t(title), anchor="w", fill=P["text"] if self.active else P["muted"],
                         font=font(10, "bold" if self.active else "normal"))


class AgentRow(tk.Canvas):
    def __init__(self, parent, agent, on_toggle, height=48):
        super().__init__(parent, height=height, bg=P["side"], highlightthickness=0, cursor="hand2")
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
            rrect(self, 0, 0, w, h, 14, fill=P["card"], outline="")
        c = color_for(self.agent.name)
        self.create_oval(8, h / 2 - 15, 38, h / 2 + 15, fill=c if self.on else P["line"], outline="")
        self.create_text(23, h / 2, text=self.agent.name[:1].upper(), fill="white", font=font(11, "bold"))
        self.create_text(50, h / 2 - 8, text=self.agent.name, anchor="w", font=font(10, "bold"),
                         fill=P["text"] if self.on else P["muted"])
        self.create_text(50, h / 2 + 9, text=i18n.t(SHORT_TYPE.get(self.agent.kind, self.agent.kind)), anchor="w",
                         font=font(8), fill=P["muted"])
        self.create_oval(w - 22, h / 2 - 5, w - 12, h / 2 + 5, fill=P["ok"] if self.on else "", outline=P["ok"] if self.on else P["muted"], width=1)


_chat_ids = itertools.count(1)


class Chat:
    """Bitta suhbat: o'z tarixi, loyihasi, holati va ko'rinishi bor."""

    def __init__(self, inner, win, project):
        self.id = next(_chat_ids)
        self.inner, self.win, self.project = inner, win, project
        self.orch = None
        self.title = "Yangi suhbat"
        self.busy = self.cancelled = self.unread = False
        self.typing = self.empty = self.dots = self.who = None
        self.pending: list = []
        self.records: list[dict] = []  # ko'rinadigan xabarlar (saqlash va tiklash uchun)
        self.replayed = True
        self.todo = None  # vazifalar kartasi
        self.stream: dict[str, str] = {}  # agent -> hozir yozilayotgan (oqimli) matn
        self.live: dict = {}  # agent -> shu matn ko'rsatilayotgan vaqtinchalik qator


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
        rrect(self, 0, 0, self.W, self.H, 14, fill=fill, outline=P["accent"] if self.active else "")
        c = self.chat
        if c.busy:
            self.create_oval(12, 13, 20, 21, fill=P["accent_hi"], outline="")
        elif c.unread:
            self.create_oval(12, 13, 20, 21, fill=P["ok"], outline="")
        _nm = i18n.t(c.title)
        title = _nm if len(_nm) <= 20 else _nm[:19] + "…"
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
        self.cfg_path = cfg_path
        self.inbox: queue.Queue = queue.Queue()
        self.cfg = config.read(cfg_path)
        i18n.set_lang(self.cfg.get("lang", "uz"))
        theme.apply_palette(self.cfg.get("theme", "dark"), self.cfg.get("accent", "violet"))
        theme.setup(self)
        first_run = not config.config_path(cfg_path).exists()
        self.title("Agent Umimiy")
        w, h = fit(self, 1180, 780)
        self.minsize(min(860, w), min(560, h))
        self.mode = tk.StringVar(value="auto")
        self.selected: set[str] = set()
        self.chats: list[Chat] = []
        self.cur: Chat | None = None
        self._override: Chat | None = None
        self._polling = False
        self.ph_on = False
        self._build_sidebar()
        self._build_main()
        self.mcp = mcplib.Manager(self.cfg.get("mcp", []))
        self.asks: dict[int, dict] = {}  # ruxsat so'rovlari (telefon ham javob bera oladi)
        self._ask_ids = itertools.count(1)
        self.remote = None
        self.remote_cmds: queue.Queue = queue.Queue()
        self.web_server = None
        self._restore_chats()
        self.rebuild()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._remote_poll)
        if self.cfg.get("remote"):
            self.after(500, self.start_remote)
        if self.cfg.get("server"):
            self.after(600, self.start_server)
        if first_run:
            self.after(400, self.first_run)

    # ---------- qurilish ----------
    def _build_sidebar(self):
        side = tk.Frame(self, bg=P["side"], width=290)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        inner = tk.Frame(side, bg=P["side"], padx=16, pady=18)
        inner.pack(fill="both", expand=True)

        self.compact = self.winfo_screenheight() < 820  # noutbuk ekrani: ixchamroq panel
        c = self.compact
        logo = tk.Frame(inner, bg=P["side"])
        logo.pack(fill="x", pady=(0, 8 if c else 18))
        c = tk.Canvas(logo, width=42, height=42, bg=P["side"], highlightthickness=0)
        rrect(c, 0, 0, 42, 42, 13, fill=P["accent"], outline="")
        c.create_text(21, 21, text="A", fill="white", font=font(17, "bold"))
        c.pack(side="left")
        t = tk.Frame(logo, bg=P["side"])
        t.pack(side="left", padx=12)
        label(t, "Agent Umimiy", size=14, weight="bold").pack(anchor="w")
        label(t, i18n.t("Barcha AI bir joyda"), fg=P["muted"], size=9).pack(anchor="w")

        label(inner, i18n.t("REJIM"), fg=P["muted"], size=8, weight="bold").pack(anchor="w", pady=(2 if c else 4, 4 if c else 6))
        self.mode_rows = {}
        for k in MODES:
            r = ModeRow(inner, k, self.pick_mode, height=32 if c else 40)
            r.pack(fill="x", pady=1)
            self.mode_rows[k] = r

        label(inner, i18n.t("AGENTLAR"), fg=P["muted"], size=8, weight="bold").pack(anchor="w", pady=(8 if c else 18, 4 if c else 6))
        bottom = tk.Frame(inner, bg=P["side"])
        bottom.pack(side="bottom", fill="x")
        bh, gap = (34, 5) if c else (42, 8)
        Pill(bottom, i18n.t("＋  Yangi suhbat"), lambda: self.new_chat(), bg=P["accent"], hover=P["accent_hi"], fg="white",
             height=bh, radius=14).pack(fill="x", pady=(0, gap))
        Pill(bottom, i18n.t("⬡   Plaginlar"), self.open_plugins, bg=P["card"], hover=P["card_hi"],
             height=bh, radius=14).pack(fill="x", pady=(0, gap))
        Pill(bottom, i18n.t("⚙   Sozlamalar"), self.open_settings, bg=P["card"], hover=P["card_hi"],
             height=bh, radius=14).pack(fill="x")
        # agentlar ro'yxati: ko'p bo'lsa aylantiriladi
        holder = tk.Frame(inner, bg=P["side"])
        holder.pack(fill="both", expand=True)
        self.agent_canvas = tk.Canvas(holder, bg=P["side"], highlightthickness=0)
        self.agent_canvas.pack(fill="both", expand=True)
        self.agent_box = tk.Frame(self.agent_canvas, bg=P["side"])
        aw = self.agent_canvas.create_window((0, 0), window=self.agent_box, anchor="nw")
        self.agent_box.bind("<Configure>", lambda e: self.agent_canvas.configure(scrollregion=self.agent_canvas.bbox("all")))
        self.agent_canvas.bind("<Configure>", lambda e: self.agent_canvas.itemconfig(aw, width=e.width))

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
        self.entry.bind("<<Paste>>", self._paste)
        self.entry.bind("<KeyRelease>", lambda e: self._grow())
        self.entry.bind("<FocusIn>", lambda e: self._ph(False))
        self.entry.bind("<FocusOut>", lambda e: self._ph(True))
        self._ph(True)

    def _wheel(self, e):
        try:
            top = e.widget.winfo_toplevel()
        except Exception:
            top = self
        if top is not self:  # boshqa oynalar (sozlamalar va h.k.) o'zi aylantiradi
            return
        if str(e.widget).startswith(str(self.agent_canvas)):  # chap paneldagi agentlar ro'yxati
            if self.agent_canvas.yview() != (0.0, 1.0):
                self.agent_canvas.yview_scroll(-2 if (e.num == 4 or e.delta > 0) else 2, "units")
            return
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
            self.entry.insert("1.0", i18n.t("Xabar yozing…   (Enter — yuborish, Shift+Enter — yangi qator)"))
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
        self.title_lbl.config(text=i18n.t(title))
        note = "  ·  " + i18n.t("loyihada faqat o'qiydi") if self.project and key in READ_ONLY_MODES else ""
        self.sub_lbl.config(text=i18n.t(desc) + note)

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
        self.count_lbl.config(text=f"●  {len(self.selected)} " + i18n.t("agent faol"))

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
        o.ctx.browser = bool(self.cfg.get("browser", True))
        o.ctx.mcp = self.mcp
        o.ctx.skills = bool(self.cfg.get("skills", True))
        o.ctx.files_dir = str(FILES_DIR)
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
            AgentRow(self.agent_box, a, self.toggle_agent, height=40 if self.compact else 48).pack(fill="x", pady=1)
        self.pick_mode(self.mode.get())
        self._count()

    # ---------- suhbatlar (tablar) ----------
    def new_chat(self, show=True):
        proj = self.cfg.get("project") or ""
        inner = tk.Frame(self.canvas, bg=P["bg"])
        win = self.canvas.create_window((0, 0), window=inner, anchor="nw", width=max(1, self.canvas.winfo_width()))
        chat = Chat(inner, win, proj if proj and Path(proj).is_dir() else "")
        inner.bind("<Configure>", lambda e: self._region() if self.cur is chat else None)
        chat.orch = self._make_orch(chat)
        self.chats.append(chat)
        with self._as(chat):
            self._show_empty()
        if show:
            self.switch(chat)
            self._save_soon()

    # ---------- saqlash va tiklash ----------
    def _on_close(self):
        from . import browser
        browser.shutdown()
        self.mcp.shutdown()
        self.stop_remote()
        self.stop_server()
        self._save_chats()
        self.destroy()

    def _save_soon(self):
        if getattr(self, "_save_job", None) is None and self.cfg.get("save_chats", True):
            self._save_job = self.after(800, self._save_chats)

    def _save_chats(self):
        self._save_job = None
        if not self.cfg.get("save_chats", True) or not self.chats:
            return
        data = [{"title": c.title, "project": c.project, "history": c.orch.history, "records": c.records}
                for c in self.chats]
        chatstore.save(data, self.chats.index(self.cur) if self.cur in self.chats else 0)

    def _restore_chats(self):
        if not self.cfg.get("save_chats", True):
            return
        data = chatstore.load()
        for saved in data["chats"]:
            self.new_chat(show=False)
            c = self.chats[-1]
            c.title = saved.get("title") or "Suhbat"
            proj = saved.get("project") or ""
            c.project = proj if proj and Path(proj).is_dir() else ""
            c.orch.ctx.root = c.project or None
            c.orch.history = list(saved.get("history", []))
            c.records, c.replayed = list(saved.get("records", [])), False
            if c.empty is not None:
                c.empty.destroy()
                c.empty = None
        if self.chats:
            self.switch(self.chats[min(data.get("active", 0), len(self.chats) - 1)])

    def _replay(self, chat):
        chat.replayed = True
        self._replaying = True
        try:
            with self._as(chat):
                for r in chat.records:
                    if r["k"] == "user":
                        self.add_user(r["text"], r.get("files", []))
                    elif r["k"] == "agent":
                        self.add_agent(r["name"], r["text"], r.get("meta", ""), r.get("err", False))
                    elif r["k"] == "act":
                        self.add_activity(r["agent"], r["kind"], r["text"])
        finally:
            self._replaying = False

    def clear_history(self):
        chatstore.clear()
        for c in list(self.chats):
            self.close_chat(c)

    def switch(self, chat):
        self.cur = chat
        chat.unread = False
        if not chat.replayed:
            self._replay(chat)
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
        self._save_soon()

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

    def _paste(self, e):
        """Ctrl+V: clipboard'da matn bo'lsa odatdagidek qo'yiladi, aks holda skrinshot/fayl biriktiriladi."""
        try:
            if self.clipboard_get():
                return None
        except tk.TclError:
            pass
        try:
            atts = attachments.from_clipboard(config.upload_dir())
        except attachments.AttachError as exc:
            messagebox.showwarning("Fayl biriktirilmadi", str(exc), parent=self)
            return "break"
        if not atts:
            return None
        self.cur.pending.extend(atts)
        self._render_chips()
        return "break"

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
            self.proj_btn.set_text(i18n.t("Loyiha:") + "  " + (name if len(name) < 22 else name[:20] + "…"))
            if not self.clear_btn.winfo_ismapped():
                self.clear_btn.pack(side="right", padx=(0, 8), before=self.proj_btn)
        else:
            self.proj_btn.set_text(i18n.t("Loyiha papkasini tanlash"))
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
            return messagebox.showinfo("Git", i18n.t("Avval «Loyiha papkasini tanlash» tugmasi bilan papkani tanlang."), parent=self)
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
            if messagebox.askyesno(i18n.t("Xush kelibsiz!"), i18n.t("Kompyuteringizda quyidagi agentlar topildi:") +
                                   f"\n\n{names}\n\n" + i18n.t("Hammasini qo'shaymi?"), parent=self):
                self.cfg["agents"] += found
                config.write(self.cfg, self.cfg_path)
                return self.rebuild()
        messagebox.showinfo(i18n.t("Xush kelibsiz!"),
                            i18n.t("Boshlash uchun «Sozlamalar» da agent qo'shing (Claude, ChatGPT, Gemini yoki lokal model)."),
                            parent=self)
        self.open_settings()

    # ---------- telefondan boshqarish ----------
    def start_remote(self):
        if self.remote:
            return
        if not self.cfg.get("remote_token"):
            self.cfg["remote_token"] = remotelib.new_token()
        self.cfg["remote"] = True
        config.write(self.cfg, self.cfg_path)
        self.remote = remotelib.RemoteServer(self._remote_call, self.cfg["remote_token"], int(self.cfg.get("remote_port", 8765)))
        try:
            self.remote.start()
        except OSError as exc:
            self.remote = None
            messagebox.showerror("Mobil kirish", f"Server ochilmadi: {exc}", parent=self)

    def stop_remote(self):
        if self.remote:
            self.remote.stop()
            self.remote = None

    def new_remote_token(self):
        self.cfg["remote_token"] = remotelib.new_token()
        config.write(self.cfg, self.cfg_path)
        if self.remote:
            self.remote.token = self.cfg["remote_token"]

    def open_remote(self):
        RemoteDialog(self)

    # ---------- veb-server ----------
    def start_server(self):
        """Veb-serverni yoqadi va sozlamaga yozadi: keyingi safar dastur ochilganda o'zi ishga tushadi."""
        if self.web_server:
            return
        self.cfg["server"] = True
        config.write(self.cfg, self.cfg_path)
        try:
            self.web_server = serverlib.start("0.0.0.0", int(self.cfg.get("server_port", 8080)), self.cfg_path)
        except OSError as exc:
            messagebox.showerror(i18n.t("Veb-server"), f"{i18n.t('Server ochilmadi:')} {exc}", parent=self)

    def stop_server(self):
        if self.web_server:
            serverlib.stop(self.web_server)
            self.web_server = None

    def open_server(self):
        ServerDialog(self)

    def _remote_call(self, action, payload):
        """Server oqimidan chaqiriladi: amalni asosiy (Tk) oqimda bajartirib, natijani kutadi."""
        q: queue.Queue = queue.Queue()
        self.remote_cmds.put((action, payload, q))
        try:
            kind, val = q.get(timeout=25)
        except queue.Empty:
            raise RuntimeError("Dastur band, javob bermadi. Qayta urining.")
        if kind == "err":
            raise ValueError(val)
        return val

    def _remote_poll(self):
        while True:
            try:
                action, payload, q = self.remote_cmds.get_nowait()
            except queue.Empty:
                break
            try:
                q.put(("ok", self._remote_exec(action, payload)))
            except Exception as exc:
                q.put(("err", str(exc)))
        self.after(120, self._remote_poll)

    def _chat_by_id(self, cid):
        return next((c for c in self.chats if c.id == cid), None)

    def _remote_exec(self, action, p):
        if action == "state":
            chat = self._chat_by_id(p.get("chat")) or self.cur
            since = p.get("since", 0)
            reset = since > len(chat.records) or chat is not self._chat_by_id(p.get("chat"))
            recs = chat.records if reset else chat.records[since:]
            chat.unread = False if chat is not self.cur else chat.unread
            targets = [n for n in chat.orch.agents if n in self.selected]
            return {"chats": [{"id": c.id, "title": c.title, "busy": c.busy, "unread": c.unread, "project": c.project}
                              for c in self.chats],
                    "chat": chat.id, "records": recs, "total": len(chat.records), "reset": reset, "busy": chat.busy,
                    "typing": targets[:1] if self.mode.get() == "single" else targets,
                    "asks": [{k: v for k, v in a.items() if k != "dialog"} for a in self.asks.values()],
                    "mode": self.mode.get(), "modes": {k: i18n.t(v[1]) for k, v in MODES.items()},
                    "agents": [{"name": n, "on": n in self.selected} for n in chat.orch.agents]}
        if action == "new":
            self.new_chat(show=False)
            self._render_tabs()
            return {"id": self.chats[-1].id}
        if action == "mode":
            if p.get("mode") not in MODES:
                raise ValueError("Noma'lum rejim")
            self.pick_mode(p["mode"])
            return {"ok": True}
        if action == "approve":
            a = self.asks.get(int(p.get("id", 0)))
            if not a:
                raise ValueError("Bu so'rov allaqachon yopilgan")
            if p.get("answer") not in ("yes", "always", "no"):
                raise ValueError("Noto'g'ri javob")
            a["dialog"]._done(p["answer"])
            return {"ok": True}
        chat = self._chat_by_id(p.get("chat"))
        if chat is None:
            raise ValueError("Suhbat topilmadi")
        if action == "stop":
            chat.cancelled = True
            chat.orch.ctx.cancel.set()
            if chat.typing is not None and chat.who is not None:
                chat.who.config(text="  " + i18n.t("To'xtatilmoqda…"))
            return {"ok": True}
        if action == "close":
            self.close_chat(chat)
            return {"ok": True}
        if action == "send":
            if chat.busy:
                raise ValueError("Agent hozir band. To'xtatib, qayta urining.")
            text = p.get("text", "")
            files = p.get("files") or []
            if not isinstance(text, str) or len(text) > serverlib.MAX_PROMPT:
                raise ValueError(f"Xabar {serverlib.MAX_PROMPT} belgidan oshmasin.")
            if not isinstance(files, list) or len(files) > serverlib.MAX_FILES or any(not isinstance(f, dict) for f in files):
                raise ValueError(f"Ko'pi bilan {serverlib.MAX_FILES} ta fayl yuborish mumkin.")
            atts = []
            try:
                for f in files:
                    atts.append(self._remote_attachment(f))
                text = text.strip()
                if not text and not atts:
                    raise ValueError("Xabar bo'sh")
                self._dispatch(chat, text, atts)
            except Exception:
                for att in atts:
                    try:
                        Path(att.path).unlink(missing_ok=True)
                    except OSError:
                        pass
                raise
            return {"ok": True}
        raise ValueError("Noma'lum amal")

    def _remote_attachment(self, f):
        try:
            return attachments.save_upload(config.upload_dir(), f.get("name", "fayl"), f.get("data", ""))
        except attachments.AttachError as exc:
            raise ValueError(str(exc))

    def open_plugins(self):
        PluginsDialog(self, self.cfg, self.mcp, self._save_plugins)

    def _save_plugins(self, mcp_cfg):
        self.cfg["mcp"] = mcp_cfg
        config.write(self.cfg, self.cfg_path)
        self.mcp.configure(mcp_cfg)

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
        label(box, i18n.t("Qanday yordam bera olaman?"), size=22, weight="bold").pack(pady=(18, 4))
        label(box, i18n.t("Agent sozlanmagan — chap pastdagi «Sozlamalar» orqali qo'shing.") if demo else
              (i18n.t("Loyiha:") + f" {self.project}\n" + i18n.t("Agentlar fayllarni o'qiydi va ruxsatingiz bilan o'zgartiradi.") if self.project else
               i18n.t("Savolingizni yozing — agentlaringiz birgalikda javob beradi.")), fg=P["muted"], size=11).pack()
        chips = tk.Frame(box, bg=P["bg"])
        chips.pack(pady=26)
        for i, s in enumerate(i18n.t(x) for x in (PROJECT_SUGGESTIONS if self.project else SUGGESTIONS)):
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
        t.tag_configure("ic", font=font(10, mono=True), background=P["code"], foreground="#c9d1ff")
        t.tag_configure("code", font=font(10, mono=True), background=P["code"], foreground="#c9d1ff",
                        lmargin1=8, lmargin2=8, rmargin=8, spacing1=2, spacing3=2)
        t.tag_configure("table", font=font(10, mono=True), foreground="#c9d1ff", wrap="none")
        for n, sz in (("h1", 16), ("h2", 14), ("h3", 12)):
            t.tag_configure(n, font=font(sz, "bold"), spacing1=6)
        segs = markdown.parse(text)
        for seg, tags in segs:
            t.insert("end", seg, tags)
            for tg in tags:
                if tg.startswith("link:") and not t.tag_cget(tg, "underline"):
                    t.tag_configure(tg, foreground=P["accent_hi"], underline=True)
                    t.tag_bind(tg, "<Button-1>", lambda e, u=tg[5:]: webbrowser.open(u))
                    t.tag_bind(tg, "<Enter>", lambda e: t.config(cursor="hand2"))
                    t.tag_bind(tg, "<Leave>", lambda e: t.config(cursor="xterm"))
        plain = [markdown.plain(segs)]
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

    def _record(self, **rec):
        if not getattr(self, "_replaying", False):
            self._a.records.append(rec)
            self._save_soon()

    def add_user(self, text, files=()):
        self._record(k="user", text=text, files=[getattr(a, "name", a) for a in files])
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=8)
        col = tk.Frame(row, bg=P["bg"])
        col.pack(side="right")
        if files:
            label(col, "   ".join(("▣ " if getattr(a, "kind", "") == "image" else "▤ ") + getattr(a, "name", a) for a in files), fg=P["muted"],
                  size=9).pack(anchor="e", pady=(0, 4))
        self._bubble(col, text, P["user"], "white").pack(anchor="e")
        self._scroll()

    def add_agent(self, name, text, meta="", err=False):
        self._record(k="agent", name=name, text=text, meta=meta, err=err)
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
            cp = label(col, i18n.t("Nusxalash"), fg=P["muted"], size=8, cursor="hand2")
            cp.pack(anchor="w", pady=(3, 0))
            cp.bind("<Button-1>", lambda e, t=text, w=cp: (self._copy(t), w.config(text=i18n.t("Nusxalandi ✓"), fg=P["ok"])))
        self._scroll()

    def _todo_card(self, text):
        chat = self._a
        try:
            items = json.loads(text)
        except ValueError:
            return
        if chat.todo is not None and chat.todo.winfo_exists():
            chat.todo.destroy()
        card = tk.Frame(self.inner, bg=P["card"], padx=14, pady=10, highlightthickness=1, highlightbackground=P["line"])
        card.pack(anchor="w", padx=(74, 28), pady=6)
        done = sum(1 for i in items if i.get("status") == "completed")
        label(card, f"Reja  ·  {done}/{len(items)}", fg=P["muted"], size=9, weight="bold").pack(anchor="w", pady=(0, 4))
        for i in items:
            st = i.get("status")
            mark, col = ("☑", P["ok"]) if st == "completed" else ("◐", P["accent_hi"]) if st == "in_progress" else ("☐", P["muted"])
            row = tk.Frame(card, bg=P["card"])
            row.pack(anchor="w")
            label(row, mark + "  ", fg=col, size=11).pack(side="left")
            label(row, i.get("content", ""), fg=P["muted"] if st == "completed" else P["text"], size=10,
                  wraplength=560, justify="left").pack(side="left")
        chat.todo = card
        if chat.typing is not None:
            chat.typing.pack_forget()
            chat.typing.pack(fill="x", padx=28, pady=8)
        self._scroll()

    def add_activity(self, agent, kind, text):
        self._record(k="act", agent=agent, kind=kind, text=text)
        if kind == "todo":
            return self._todo_card(text)
        self._clear_empty()
        row = tk.Frame(self.inner, bg=P["bg"])
        row.pack(fill="x", padx=28, pady=1)
        if kind == "file":  # agent yaratgan fayl: bosilsa ochiladi
            row.pack_configure(pady=4)
            link = label(row, f"📄  {Path(text).name}   —   " + i18n.t("Ochish"), fg=P["accent_hi"], size=10, cursor="hand2")
            link.pack(side="left", padx=(46, 0))
            link.bind("<Button-1>", lambda e, p=text: open_path(p) or messagebox.showinfo(i18n.t("Fayl"), p, parent=self))
            folder = label(row, "    " + i18n.t("Papkani ochish"), fg=P["muted"], size=9, cursor="hand2")
            folder.pack(side="left")
            folder.bind("<Button-1>", lambda e, p=text: open_path(Path(p).parent))
        else:
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
            self.who.config(text="  " + i18n.t("To'xtatilmoqda…"))

    def send(self):
        if self.busy:
            return self.stop()
        chat = self.cur
        prompt, files = self._text(), list(chat.pending)
        if not prompt and not files:
            return
        self.entry.delete("1.0", "end")
        self._grow()
        chat.pending = []
        self._render_chips()
        self._dispatch(chat, prompt, files)

    def _dispatch(self, chat, prompt, files):
        """Xabarni agentlarga yuboradi (oynadan ham, telefondan ham shu yo'l)."""
        prompt = prompt or "Biriktirilgan fayl(lar)ni ko'rib chiq va qisqacha tushuntir."
        if not chat.replayed:
            self._replay(chat)
        with self._as(chat):
            if chat.title == "Yangi suhbat":
                chat.title = prompt.replace("\n", " ")[:22]
            self._save_soon()
            self.add_user(prompt, files)
            mode = self.mode.get()
            targets = [n for n in self.orch.agents if n in self.selected]
            shown = targets[:1] if mode == "single" else targets
            chat.busy, chat.cancelled = True, False
            self._typing_on(shown)
        self._render_tabs()
        if chat is self.cur:
            self._send_draw(False)
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
        streamed = []  # oqimli matni o'zgargan suhbatlar: navbat bo'shagach bir marta chiziladi
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
                if item[0] == "event" and item[3] in ("delta", "turn"):
                    chat.stream[item[2]] = "" if item[3] == "turn" else chat.stream.get(item[2], "") + item[4]
                    if chat not in streamed:
                        streamed.append(chat)
                elif item[0] == "event":
                    self.add_activity(*item[2:])
                elif item[0] == "ask":
                    _, _, agent, kind, title, detail, box, evt = item
                    if chat.cancelled:
                        box[0] = "no"
                    else:
                        d = ApproveDialog(self, f"{agent} · {chat.title}", kind, title, detail)
                        aid = next(self._ask_ids)
                        self.asks[aid] = {"id": aid, "chat": chat.id, "agent": f"{agent} · {chat.title}", "kind": kind,
                                          "title": title, "detail": detail, "dialog": d}
                        self.wait_window(d)
                        self.asks.pop(aid, None)
                        box[0] = d.result
                    evt.set()
                else:
                    self._done(item[2], item[3])
        for chat in streamed:
            if chat in self.chats:
                with self._as(chat):
                    self._render_live()
        if any(c.busy for c in self.chats):
            self.after(100, self._poll)
        else:
            self._polling = False

    def _render_live(self):
        """Oqimli javob: matn kelishi bilan vaqtinchalik qatorda ko'rsatiladi; yakuniy javob uni almashtiradi."""
        chat = self._a
        for agent, text in chat.stream.items():
            row = chat.live.get(agent)
            if not text:
                if row is not None:
                    row.destroy()
                    del chat.live[agent]
                continue
            if row is None:
                self._clear_empty()
                row = chat.live[agent] = tk.Frame(chat.inner, bg=P["bg"])
                row.pack(fill="x", padx=28, pady=8)
                Avatar(row, agent).pack(side="left", anchor="n", padx=(0, 12))
                row.body = label(row, "", size=11, wraplength=self._max_w(), justify="left")
                row.body.pack(side="left", anchor="w")
            row.body.config(text=text)
        if chat.typing is not None:
            chat.typing.pack_forget()
            chat.typing.pack(fill="x", padx=28, pady=8)
        self._scroll()

    def _done(self, results, error):
        chat = self._a
        for row in chat.live.values():
            row.destroy()
        chat.stream, chat.live = {}, {}
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
