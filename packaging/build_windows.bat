@echo off
REM Windows'da ishga tushiring: build_windows.bat
REM Natija: dist\AgentUmimiy\AgentUmimiy.exe  (+ installer, agar Inno Setup o'rnatilgan bo'lsa)
python -m pip install --upgrade pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --name AgentUmimiy app.py || exit /b 1
where iscc >nul 2>nul && iscc packaging\installer.iss
echo Tayyor: dist\AgentUmimiy\AgentUmimiy.exe
