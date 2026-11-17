@echo off
REM Windows'da ishga tushiring: build_windows.bat
REM Natija: dist\RMSAI\RMSAI.exe  (+ installer, agar Inno Setup o'rnatilgan bo'lsa)
REM Yangi interfeys (Node.js kerak): natija rms_aistaticweb papkasiga tushadi
pushd frontend && call npm install && call npm run build && popd || exit /b 1
python -m pip install --upgrade pyinstaller pypdf qrcode pillow python-docx openpyxl python-pptx pywebview || exit /b 1
if not exist build\tcl_probe mkdir build\tcl_probe
xcopy "%LOCALAPPDATA%\Programs\Python\Python313\tcl\tcl8.6" "build\tcl_probe\tcl8.6" /E /I /Y >nul
xcopy "%LOCALAPPDATA%\Programs\Python\Python313\tcl\tk8.6" "build\tcl_probe\tk8.6" /E /I /Y >nul
xcopy "%LOCALAPPDATA%\Programs\Python\Python313\tcl\tcl8" "build\tcl_probe\tcl8" /E /I /Y >nul
set "TCL_LIBRARY=%CD:\=/%/build/tcl_probe/tcl8.6"
set "TK_LIBRARY=%CD:\=/%/build/tcl_probe/tk8.6"
python -m PyInstaller --noconfirm --clean --windowed --hidden-import tkinter --hidden-import _tkinter --hidden-import pypdf --hidden-import qrcode --hidden-import PIL.ImageGrab --hidden-import webview --runtime-hook packaging/rthook_tkinter.py --icon packaging/RMSAI.ico --add-data "rms_ai/static;rms_ai/static" --add-data "packaging/RMSAI.ico;." --name RMSAI app.py || exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --hidden-import webview --icon packaging/RMSAI.ico --name RMSAIClient client_app.py || exit /b 1
where iscc >nul 2>nul && (
    iscc packaging\installer.iss
    iscc packaging\client_installer.iss
)
echo Tayyor: dist\RMSAI\RMSAI.exe va dist\RMSAIClient\RMSAIClient.exe
