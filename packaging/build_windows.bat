@echo off
REM Windows'da ishga tushiring: build_windows.bat
REM Natija: dist\AgentUmimiy\AgentUmimiy.exe  (+ installer, agar Inno Setup o'rnatilgan bo'lsa)
python -m pip install --upgrade pyinstaller pywebview pypdf qrcode pillow python-docx openpyxl python-pptx || exit /b 1
pushd frontend
call npm install || exit /b 1
call npm run build || exit /b 1
if not exist ..\agent_umimiy\static\web mkdir ..\agent_umimiy\static\web
xcopy /E /I /Y dist\* ..\agent_umimiy\static\web\ >nul || exit /b 1
popd
python -m PyInstaller --noconfirm --clean --windowed --hidden-import pypdf --hidden-import qrcode --hidden-import PIL.ImageGrab --collect-all webview --add-data "agent_umimiy/static;agent_umimiy/static" --name AgentUmimiy app.py || exit /b 1
where iscc >nul 2>nul && iscc packaging\installer.iss
echo Tayyor: dist\AgentUmimiy\AgentUmimiy.exe

