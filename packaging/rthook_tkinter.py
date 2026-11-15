"""Make the Tcl/Tk data bundled with the app visible to the Tcl runtime.

Without this the frozen app cannot start Tk: the classic window dies silently
(--windowed means there is no console to show the error in).
"""

import os
import sys

if getattr(sys, "frozen", False):
    root = sys._MEIPASS.replace("\\", "/")
    for var, name in (("TCL_LIBRARY", "_tcl_data"), ("TK_LIBRARY", "_tk_data")):
        path = root + "/" + name
        if os.path.isdir(path):  # faqat haqiqatan mavjud bo'lsa: aks holda Tk butunlay ishlamay qoladi
            os.environ[var] = path
