"""Git bilan oddiy ishlash (GUI uchun). Barcha xabarlar oddiy tilda."""
from __future__ import annotations

import shutil
import subprocess

from . import proc

WORDS = {"M": "o'zgargan", "A": "yangi (qo'shilgan)", "D": "o'chirilgan", "R": "nomi o'zgargan",
         "??": "yangi (hali saqlanmagan)", "U": "to'qnashuv"}


def have_git() -> bool:
    return shutil.which("git") is not None


def run(root: str, *args: str, timeout: int = 120) -> tuple[bool, str]:
    try:
        p = proc.run(["git", *args], cwd=root, timeout=timeout, encoding="utf-8")
    except FileNotFoundError:
        return False, "Git o'rnatilmagan. git-scm.com dan o'rnating."
    except subprocess.TimeoutExpired:
        return False, "Vaqt tugadi (internet yoki parol so'ralayotgan bo'lishi mumkin)."
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def is_repo(root: str) -> bool:
    return run(root, "rev-parse", "--is-inside-work-tree")[0]


def branch(root: str) -> str:
    ok, out = run(root, "symbolic-ref", "--short", "HEAD")  # birinchi commitdan oldin ham ishlaydi
    return out if ok else ""


def status(root: str) -> list[tuple[str, str]]:
    ok, out = run(root, "status", "--porcelain")
    rows = []
    for line in out.splitlines() if ok else []:
        code, path = line[:2].strip(), line[3:]
        rows.append((WORDS.get(code, WORDS.get(code[:1], code)), path))
    return rows


def diff(root: str) -> str:
    ok, out = run(root, "diff", "HEAD")
    if not ok:  # birinchi commit hali yo'q
        ok, out = run(root, "diff")
    return out or "(farq yo'q)"


def commit_all(root: str, message: str) -> tuple[bool, str]:
    ok, out = run(root, "add", "-A")
    if not ok:
        return ok, out
    ok, out = run(root, "commit", "-m", message)
    if not ok and ("user.email" in out or "user.name" in out or "Please tell me who you are" in out):
        out += "\n\nIsmingizni sozlang: git config --global user.name \"Ismingiz\" va user.email \"pochta@...\""
    return ok, out
