"""Dizayn: ranglar, shriftlar va maxsus chizilgan vidjetlar (Tkinter'ning oddiy ko'rinishidan qutulish uchun)."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

P = dict(
    bg="#0d0f16", side="#121521", card="#1a1e2e", card_hi="#232842", line="#2a3047",
    text="#e8eaf4", muted="#8b92ab", accent="#7c6cff", accent_hi="#9a8dff",
    user="#5a49ee", ok="#34d399", err="#f87171", code="#080a10", warn="#fbbf24",
)
AVATARS = ["#7c6cff", "#22d3ee", "#f59e0b", "#ec4899", "#34d399", "#f97316", "#60a5fa", "#a3e635"]
FAMILY = "Segoe UI"
MONO = "Consolas"


def color_for(name: str) -> str:
    return AVATARS[sum(map(ord, name)) % len(AVATARS)]


def font(size=10, weight="normal", mono=False):
    return tkfont.Font(family=MONO if mono else FAMILY, size=size, weight=weight)


def rrect(c: tk.Canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def setup(root: tk.Misc):
    """ttk va ochiladigan ro'yxatlarni qorong'i mavzuga o'tkazadi."""
    root.configure(bg=P["bg"])
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=P["bg"], foreground=P["text"], fieldbackground=P["card"], font=(FAMILY, 10))
    st.configure("TEntry", fieldbackground=P["card"], foreground=P["text"], bordercolor=P["line"],
                 lightcolor=P["line"], darkcolor=P["line"], insertcolor=P["text"], padding=6)
    st.configure("TCombobox", fieldbackground=P["card"], background=P["card_hi"], foreground=P["text"],
                 arrowcolor=P["muted"], bordercolor=P["line"], lightcolor=P["line"], darkcolor=P["line"],
                 selectbackground=P["card"], selectforeground=P["text"], padding=6)
    st.map("TCombobox", fieldbackground=[("readonly", P["card"])], foreground=[("readonly", P["text"])],
           selectbackground=[("readonly", P["card"])], selectforeground=[("readonly", P["text"])])
    st.configure("Treeview", background=P["card"], fieldbackground=P["card"], foreground=P["text"],
                 bordercolor=P["line"], rowheight=30, borderwidth=0)
    st.map("Treeview", background=[("selected", P["accent"])], foreground=[("selected", "white")])
    st.configure("Treeview.Heading", background=P["card_hi"], foreground=P["muted"], relief="flat", padding=6)
    st.configure("Vertical.TScrollbar", background=P["card_hi"], troughcolor=P["bg"], bordercolor=P["bg"],
                 arrowcolor=P["bg"], lightcolor=P["card_hi"], darkcolor=P["card_hi"], gripcount=0, relief="flat")
    st.map("Vertical.TScrollbar", background=[("active", P["accent"])])
    root.option_add("*TCombobox*Listbox.background", P["card"])
    root.option_add("*TCombobox*Listbox.foreground", P["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", P["accent"])
    root.option_add("*TCombobox*Listbox.font", (FAMILY, 10))


class Pill(tk.Canvas):
    """Yumaloq tugma."""

    def __init__(self, parent, text, command, bg=None, hover=None, fg=None, height=36, radius=12,
                 width=None, size=10, weight="bold", anchor="center", outline=None):
        self.parent_bg = parent["bg"]
        super().__init__(parent, height=height, highlightthickness=0, bg=self.parent_bg, cursor="hand2",
                         **({"width": width} if width else {}))
        self.text, self.command, self.radius, self.anchor = text, command, radius, anchor
        self.bg, self.hover = bg or P["card"], hover or P["card_hi"]
        self.fg, self.outline = fg or P["text"], outline
        self.f = font(size, weight)
        self.over = False
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<Button-1>", lambda e: self.command and self.command())

    def _set(self, v):
        self.over = v
        self.draw()

    def set_text(self, text):
        self.text = text
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        rrect(self, 1, 1, w - 1, h - 1, self.radius, fill=self.hover if self.over else self.bg,
              outline=self.outline or "", width=1 if self.outline else 0)
        if self.anchor == "center":
            self.create_text(w / 2, h / 2, text=self.text, fill=self.fg, font=self.f)
        else:
            self.create_text(14, h / 2, text=self.text, fill=self.fg, font=self.f, anchor="w")


class Avatar(tk.Canvas):
    def __init__(self, parent, name, size=34):
        super().__init__(parent, width=size, height=size, bg=parent["bg"], highlightthickness=0)
        self.create_oval(1, 1, size - 1, size - 1, fill=color_for(name), outline="")
        self.create_text(size / 2, size / 2, text=(name[:1] or "?").upper(), fill="white",
                         font=font(max(9, size // 3), "bold"))


def label(parent, text="", fg=None, size=10, weight="normal", bg=None, **kw):
    return tk.Label(parent, text=text, fg=fg or P["text"], bg=bg or parent["bg"], font=font(size, weight), **kw)
