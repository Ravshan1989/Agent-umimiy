"""subprocess o'rami: oynasiz (--windowed) .exe ichida ham xatosiz ishlashi uchun."""
from __future__ import annotations

import os
import signal
import subprocess

KILL_GRACE = 10  # o'ldirilgandan keyin quvurlar yopilishini shuncha kutamiz


def _kill_tree(p: subprocess.Popen) -> None:
    """Jarayonni bolalari bilan birga o'ldiradi.

    shell=True bilan faqat cmd.exe (yoki sh) o'ldirilsa, haqiqiy buyruq ishlashda davom etadi
    va quvurlar yopilmagani uchun communicate() chegaradan keyin ham kutib turadi.
    """
    try:
        if os.name == "nt":
            # timeout shart: taskkill qotib qolsa, buyruq chegarasi butunlay ma'nosiz bo'lib qoladi.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, timeout=KILL_GRACE,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        p.kill()
    except OSError:
        pass


def run(args, *, cwd=None, input=None, timeout=None, shell=False, encoding=None):
    kw = {} if input is not None else {"stdin": subprocess.DEVNULL}  # stdin yo'q bo'lsa Windows'da xato beradi
    if os.name != "nt":
        kw["start_new_session"] = True  # butun guruhni o'ldira olish uchun
    # `with` shart: har qanday istisnoda (timeout, KeyboardInterrupt) bola o'ldiriladi va quvurlar yopiladi.
    with subprocess.Popen(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE if input is not None else kw.pop("stdin"),
        text=True, encoding=encoding, errors="replace", shell=shell,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, **kw,
    ) as p:
        try:
            out, err = p.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(p)
            try:
                out, err = p.communicate(timeout=KILL_GRACE)
            except subprocess.TimeoutExpired:  # quvurni nevara jarayon ushlab turibdi: kutmaymiz
                out = err = ""
            raise subprocess.TimeoutExpired(args, timeout, output=out, stderr=err)
        return subprocess.CompletedProcess(args, p.returncode, out, err)
