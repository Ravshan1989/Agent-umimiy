"""Agentlarga beriladigan asboblar: loyiha papkasida fayl o'qish/yozish, qidirish, buyruq ishga tushirish."""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import proc

MAX_READ = 200_000
MAX_OUT = 8000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode"}


class ToolError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class Context:
    """Agentlar ishlaydigan muhit. GUI ruxsat so'rash va hodisalarni shu orqali ulaydi."""

    root: str | None = None
    confirm: Callable[[str, str, str, str], str] | None = None  # (agent, kind, sarlavha, tafsilot) -> yes|always|no
    emit: Callable[[str, str, str], None] | None = None  # (agent, kind, matn)
    readonly: bool = False
    always: set = field(default_factory=set)
    cancel: threading.Event = field(default_factory=threading.Event)

    @property
    def active(self) -> bool:
        return bool(self.root)


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    kind: str  # read | write | run


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


S = {"type": "string"}
TOOLS = [
    Tool("list_dir", "List files and folders in a directory of the project (relative path, empty = project root).",
         _obj({"path": S}), "read"),
    Tool("read_file", "Read a text file. Optional 1-based line offset and limit for large files.",
         _obj({"path": S, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["path"]), "read"),
    Tool("search_files", "Search file contents with a regular expression. Optional path (subfolder) and glob (e.g. *.py).",
         _obj({"pattern": S, "path": S, "glob": S}, ["pattern"]), "read"),
    Tool("write_file", "Create a file or overwrite it completely with the given content. Asks the user for permission.",
         _obj({"path": S, "content": S}, ["path", "content"]), "write"),
    Tool("edit_file", "Replace old_string with new_string in a file. old_string must match exactly once unless "
         "replace_all is true. Asks the user for permission.",
         _obj({"path": S, "old_string": S, "new_string": S, "replace_all": {"type": "boolean"}},
              ["path", "old_string", "new_string"]), "write"),
    Tool("run_command", "Run a shell command in the project folder (tests, build, git commit, installs...). "
         "Asks the user for permission. Returns exit code and output.",
         _obj({"command": S, "timeout": {"type": "integer", "description": "seconds, max 300"}}, ["command"]), "run"),
    Tool("git_info", "Read-only git information: status, diff or log.",
         _obj({"what": {"type": "string", "enum": ["status", "diff", "log"]}}, ["what"]), "read"),
]
BY_NAME = {t.name: t for t in TOOLS}


def system_prompt(ctx: Context) -> str:
    text = (
        "You are a coding assistant inside the desktop app 'Agent Umimiy'. The user's project folder is "
        f"{ctx.root} (operating system: {sys.platform}). You have tools to list, read, search, create and edit files, "
        "run shell commands and read git info. Read the relevant files before changing anything, keep edits small and "
        "precise, and verify your work (e.g. by running tests) when possible. The user may be a beginner: when you "
        "finish, explain briefly in plain language what you did. Always answer in the language the user writes in. "
        "Paths are relative to the project folder."
    )
    if ctx.readonly:
        text += " IMPORTANT: in this mode you may only read; write_file, edit_file and run_command are disabled."
    return text


def _clip(s: str, n: int = MAX_OUT) -> str:
    return s if len(s) <= n else s[: n // 2] + "\n...[qisqartirildi]...\n" + s[-n // 2:]


class Toolbox:
    def __init__(self, ctx: Context, agent: str):
        self.ctx, self.agent = ctx, agent
        self.root = Path(ctx.root).resolve()

    # ---- yordamchilar ----
    def _say(self, kind, text):
        if self.ctx.emit:
            self.ctx.emit(self.agent, kind, text)

    def _path(self, p: str, write=False) -> Path:
        full = (self.root / (p or ".")).resolve()
        try:
            rel = full.relative_to(self.root)
        except ValueError:
            raise ToolError("Yo'l loyiha papkasidan tashqarida — ruxsat yo'q.")
        if write and ".git" in rel.parts:
            raise ToolError(".git papkasini o'zgartirib bo'lmaydi.")
        return full

    def _rel(self, full: Path) -> str:
        return str(full.relative_to(self.root)).replace("\\", "/") or "."

    def _approve(self, kind: str, title: str, detail: str):
        if self.ctx.readonly:
            raise ToolError("Bu rejimda faqat o'qish mumkin (o'zgartirish o'chirilgan).")
        if kind in self.ctx.always:
            return
        if not self.ctx.confirm:
            raise ToolError("Foydalanuvchidan ruxsat so'rash imkoni yo'q.")
        ans = self.ctx.confirm(self.agent, kind, title, detail)
        if ans == "always":
            self.ctx.always.add(kind)
        elif ans != "yes":
            raise ToolError("Foydalanuvchi bu amalni rad etdi.")

    # ---- ishga tushirish ----
    def run(self, name: str, args: dict) -> tuple[str, bool]:
        if self.ctx.cancel.is_set():
            raise Cancelled()
        tool = BY_NAME.get(name)
        if not tool:
            return f"Noma'lum asbob: {name}", True
        try:
            return getattr(self, "t_" + name)(**args), False
        except ToolError as exc:
            self._say("info", str(exc))
            return str(exc), True
        except TypeError as exc:
            return f"Noto'g'ri argumentlar: {exc}", True
        except Exception as exc:
            return f"Xato: {exc}", True

    # ---- asboblar ----
    def t_list_dir(self, path: str = "") -> str:
        d = self._path(path)
        if not d.is_dir():
            raise ToolError(f"Papka topilmadi: {path}")
        self._say("read", f"Papkani ko'rdi: {self._rel(d)}")
        items = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        items = [i for i in items if i.name not in SKIP_DIRS][:300]
        return "\n".join(i.name + ("/" if i.is_dir() else f"  ({i.stat().st_size} bytes)") for i in items) or "(bo'sh)"

    def _read(self, f: Path) -> str:
        if not f.is_file():
            raise ToolError(f"Fayl topilmadi: {self._rel(f)}")
        data = f.read_bytes()
        if b"\x00" in data[:2048]:
            raise ToolError("Bu ikkilik (binary) fayl, matn sifatida o'qib bo'lmaydi.")
        return data.decode("utf-8", errors="replace")

    def t_read_file(self, path: str, offset: int = 1, limit: int = 0) -> str:
        f = self._path(path)
        text = self._read(f).replace("\r\n", "\n")
        self._say("read", f"Faylni o'qidi: {self._rel(f)}")
        lines = text.split("\n")
        start = max(1, offset or 1)
        sel = lines[start - 1:(start - 1 + limit) if limit else None]
        out = "\n".join(f"{start + i:>5}  {ln}" for i, ln in enumerate(sel))
        return _clip(out, MAX_READ)

    def t_search_files(self, pattern: str, path: str = "", glob: str = "") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"Noto'g'ri regex: {exc}")
        base = self._path(path)
        self._say("read", f"Qidirdi: {pattern}")
        hits = []
        for f in sorted(base.rglob(glob or "*")):
            if len(hits) >= 100:
                break
            if not f.is_file() or any(p in SKIP_DIRS for p in f.relative_to(self.root).parts):
                continue
            try:
                if f.stat().st_size > 1_000_000:
                    continue
                text = f.read_bytes()
                if b"\x00" in text[:2048]:
                    continue
                for n, ln in enumerate(text.decode("utf-8", errors="replace").splitlines(), 1):
                    if rx.search(ln):
                        hits.append(f"{self._rel(f)}:{n}: {ln.strip()[:200]}")
                        if len(hits) >= 100:
                            break
            except OSError:
                continue
        return "\n".join(hits) or "Hech narsa topilmadi."

    def t_write_file(self, path: str, content: str) -> str:
        f = self._path(path, write=True)
        old = self._read(f) if f.exists() else None
        title = f"Fayl {'o‘zgartiriladi' if old is not None else 'yaratiladi'}: {self._rel(f)}"
        detail = _diff(old or "", content, self._rel(f)) if old is not None else _clip(content, 3000)
        self._approve("write", title, detail)
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        self._say("write", f"{'Yangiladi' if old is not None else 'Yaratdi'}: {self._rel(f)}")
        return f"OK: {self._rel(f)} yozildi ({len(content)} belgi)."

    def t_edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        f = self._path(path, write=True)
        raw = self._read(f)
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        old_string, new_string = old_string.replace("\r\n", "\n"), new_string.replace("\r\n", "\n")
        n = text.count(old_string) if old_string else 0
        if n == 0:
            raise ToolError("old_string faylda topilmadi (bo'shliqlar va qatorlar aynan mos bo'lishi kerak).")
        if n > 1 and not replace_all:
            raise ToolError(f"old_string {n} marta uchraydi; aniqroq qiling yoki replace_all=true bering.")
        new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
        self._approve("write", f"Fayl tahrirlanadi: {self._rel(f)}", _diff(text, new_text, self._rel(f)))
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text.replace("\n", "\r\n") if crlf else new_text)
        self._say("write", f"Tahrirladi: {self._rel(f)}")
        return f"OK: {self._rel(f)} tahrirlandi ({n if replace_all else 1} joy)."

    def t_run_command(self, command: str, timeout: int = 120) -> str:
        self._approve("run", "Buyruq ishga tushiriladi", f"{command}\n\n(papka: {self.root})")
        self._say("run", f"Buyruq: {command[:120]}")
        try:
            p = proc.run(command, cwd=str(self.root), shell=True, timeout=min(max(timeout or 120, 1), 300))
        except subprocess.TimeoutExpired:
            raise ToolError("Buyruq vaqti tugadi va to'xtatildi.")
        err = "\n[stderr]\n" + p.stderr if p.stderr.strip() else ""
        return _clip(f"exit code: {p.returncode}\n{p.stdout}{err}")

    def t_git_info(self, what: str) -> str:
        args = {"status": ["status", "--short", "--branch"], "diff": ["diff", "HEAD"], "log": ["log", "--oneline", "-20"]}
        if what not in args:
            raise ToolError("what: status | diff | log")
        self._say("read", f"Git: {what}")
        try:
            p = proc.run(["git", *args[what]], cwd=str(self.root), timeout=30, encoding="utf-8")
        except FileNotFoundError:
            raise ToolError("Git o'rnatilmagan.")
        return _clip((p.stdout + p.stderr).strip() or "(bo'sh)")


def _diff(old: str, new: str, name: str) -> str:
    d = list(difflib.unified_diff(old.splitlines(), new.splitlines(), f"{name} (eski)", f"{name} (yangi)", lineterm="", n=2))
    if len(d) > 80:
        d = d[:80] + [f"... yana {len(d) - 80} qator"]
    return "\n".join(d) or "(o'zgarish yo'q)"
