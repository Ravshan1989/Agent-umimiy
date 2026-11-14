"""subprocess o'rami: oynasiz (--windowed) .exe ichida ham xatosiz ishlashi uchun."""
from __future__ import annotations

import os
import signal
import subprocess

KILL_GRACE = 10  # o'ldirilgandan keyin quvurlar yopilishini shuncha kutamiz


def runtime_path() -> str:
    """Use the current PATH plus recently installed Windows user tools.

    Desktop apps can keep an old PATH after a package manager installs a tool.
    WinGet exposes user-installed executables through this stable links folder.
    """
    current = os.environ.get("PATH", "")
    if os.name != "nt":
        return current
    local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    candidates = [os.path.join(local, "Microsoft", "WinGet", "Links")]
    try:
        import winreg
        for hive, key in (
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    value, _ = winreg.QueryValueEx(handle, "Path")
                candidates.append(os.path.expandvars(value))
            except OSError:
                continue
    except ImportError:
        pass
    seen = set()
    entries = []
    for entry in [current, *candidates]:
        for item in entry.split(os.pathsep):
            item = os.path.expandvars(item.strip().strip('"'))
            if not item:
                continue
            key = os.path.normcase(os.path.normpath(item))
            if key not in seen:
                seen.add(key)
                entries.append(item)
    return os.pathsep.join(entries)


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
        env={**os.environ, "PATH": runtime_path(), "GIT_TERMINAL_PROMPT": "0"}, **kw,
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
