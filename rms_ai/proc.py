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


def _create_job(p: subprocess.Popen):
    """Attach a suspended Windows process to a Job Object before its shell can spawn children."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    if not kernel32.AssignProcessToJobObject(job, p._handle):
        kernel32.CloseHandle(job)
        return None
    return job


def _resume_process(p: subprocess.Popen) -> None:
    """Resume a Windows process created suspended so it can be assigned to its job first."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
        ntdll.NtResumeProcess.restype = wintypes.LONG
        status = ntdll.NtResumeProcess(p._handle)
        if status < 0:
            raise OSError(f"NtResumeProcess failed with NTSTATUS 0x{status & 0xFFFFFFFF:08x}")


def _terminate_job(job) -> None:
    if not job:
        return
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    try:
        kernel32.TerminateJobObject(job, 1)
    finally:
        kernel32.CloseHandle(job)


def run(args, *, cwd=None, input=None, timeout=None, shell=False, encoding=None):
    kw = {} if input is not None else {"stdin": subprocess.DEVNULL}  # stdin yo'q bo'lsa Windows'da xato beradi
    if os.name != "nt":
        kw["start_new_session"] = True  # butun guruhni o'ldira olish uchun
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if os.name == "nt":
        creationflags |= 0x00000004  # CREATE_SUSPENDED: job'ga biriktirishdan oldin shell ishlamasin
    # `with` shart: har qanday istisnoda (timeout, KeyboardInterrupt) bola o'ldiriladi va quvurlar yopiladi.
    with subprocess.Popen(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.PIPE if input is not None else kw.pop("stdin"),
        text=True, encoding=encoding, errors="replace", shell=shell,
        creationflags=creationflags,
        env={**os.environ, "PATH": runtime_path(), "GIT_TERMINAL_PROMPT": "0"}, **kw,
    ) as p:
        job = _create_job(p)
        try:
            _resume_process(p)
        except Exception:
            if job:
                _terminate_job(job)
                job = None
            _kill_tree(p)
            raise
        try:
            out, err = p.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            if job:
                _terminate_job(job)
                job = None
            else:
                _kill_tree(p)
            try:
                out, err = p.communicate(timeout=KILL_GRACE)
            except subprocess.TimeoutExpired:  # quvurni nevara jarayon ushlab turibdi: kutmaymiz
                out = err = ""
            raise subprocess.TimeoutExpired(args, timeout, output=out, stderr=err)
        finally:
            if job:
                import ctypes

                ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(job)
        return subprocess.CompletedProcess(args, p.returncode, out, err)
