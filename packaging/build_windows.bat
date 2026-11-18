@echo off
REM Windows'da ishga tushiring: build_windows.bat
REM Natija: dist\RMSAI\RMSAI.exe  (+ installer, agar Inno Setup o'rnatilgan bo'lsa)
REM Yangi interfeys (Node.js kerak): natija rms_aistaticweb papkasiga tushadi
pushd frontend && call npm ci && call npm run build && popd || exit /b 1
python -m pip install --upgrade pyinstaller pypdf qrcode pillow python-docx openpyxl python-pptx pywebview || exit /b 1
python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy()" >nul 2>nul || (echo XATO: Python tkinter/Tcl-Tk ishlamayapti. & exit /b 1)
python -m PyInstaller --noconfirm --clean --windowed --hidden-import tkinter --hidden-import _tkinter --hidden-import pypdf --hidden-import qrcode --hidden-import PIL.ImageGrab --hidden-import webview --runtime-hook packaging/rthook_tkinter.py --icon packaging/RMSAI.ico --add-data "rms_ai/static;rms_ai/static" --add-data "packaging/RMSAI.ico;." --name RMSAI app.py || exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --hidden-import webview --icon packaging/RMSAI.ico --name RMSAIClient client_app.py || exit /b 1
where iscc >nul 2>nul || (echo XATO: O'rnatuvchilar uchun Inno Setup kerak. & exit /b 1)
iscc packaging\installer.iss || exit /b 1
iscc packaging\client_installer.iss || exit /b 1
echo Tayyor: dist\RMSAI\RMSAI.exe va dist\RMSAIClient\RMSAIClient.exe
