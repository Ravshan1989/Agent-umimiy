@echo off
title RMS AI - To'liq O'rnatish va Ishga Tushirish
cd /d "%~dp0"

echo [1/4] Python virtual muhiti tekshirilmoqda...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || exit /b 1
)

echo [2/4] Kerakli agent va MCP kutubxonalari o'rnatilmoqda...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -e . --quiet || exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements-extras.txt || exit /b 1
where npm >nul 2>nul
if errorlevel 1 goto skip_frontend
echo [2b/4] Zamonaviy veb-interfeys yig'ilmoqda...
pushd frontend || exit /b 1
call npm ci --silent
if errorlevel 1 (popd & exit /b 1)
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd
:skip_frontend

echo [3/4] Konfiguratsiya va 150+ skillar nusxalanmoqda...
REM Avvalgi versiya ma'lumotlari bo'lsa, papka yaratilishidan oldin yangi nomga ko'chiriladi
".venv\Scripts\python.exe" -c "from rms_ai import config; config.user_dir()"
if not exist "%APPDATA%\RMSAI" mkdir "%APPDATA%\RMSAI"
if not exist "%APPDATA%\RMSAI\agents.json" (
    copy /Y "packaging\agents.example.json" "%APPDATA%\RMSAI\agents.json" >NUL
    if errorlevel 1 exit /b 1
)
if not exist "litellm_config.yaml" (
    copy /Y "packaging\litellm_config.example.yaml" "litellm_config.yaml" >NUL
    if errorlevel 1 exit /b 1
)
if not exist "%APPDATA%\RMSAI\skills" mkdir "%APPDATA%\RMSAI\skills"
robocopy "skills" "%APPDATA%\RMSAI\skills" /E /XC /XN /XO >NUL
if errorlevel 8 exit /b 1

echo [4/4] RMS AI ishga tushirilmoqda...
start "" ".venv\Scripts\pythonw.exe" app.py
echo Tayyor!
