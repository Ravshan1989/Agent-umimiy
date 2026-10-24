"""subprocess o'rami: oynasiz (--windowed) .exe ichida ham xatosiz ishlashi uchun."""
from __future__ import annotations

import os
import subprocess


def run(args, *, cwd=None, input=None, timeout=None, shell=False, encoding=None):
    kw = {} if input is not None else {"stdin": subprocess.DEVNULL}  # stdin yo'q bo'lsa Windows'da xato beradi
    return subprocess.run(
        args, cwd=cwd, input=input, capture_output=True, text=True, encoding=encoding, errors="replace",
        timeout=timeout, shell=shell, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, **kw,
    )
