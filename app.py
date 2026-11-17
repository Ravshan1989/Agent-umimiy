import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

if sys.platform == "win32":
    try:  # buzilgan dastur ishga tushganda Windows xato oynasi chiqib, ilovani qotirib qo'ymasin
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)  # FAILCRITICALERRORS | NOGPFAULTERRORBOX | NOOPENFILEERRORBOX
    except Exception:
        pass

from rms_ai.__main__ import main

if __name__ == "__main__":
    main()
