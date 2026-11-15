@echo off
title RMS AI - To'liq O'rnatish va Ishga Tushirish
cd /d "%~dp0"

echo [1/4] Python virtual muhiti tekshirilmoqda...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

echo [2/4] Kerakli agent va MCP kutubxonalari o'rnatilmoqda...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -e . --quiet
".venv\Scripts\python.exe" -m pip install -r requirements-extras.txt

echo [3/4] Konfiguratsiya va 150+ skillar nusxalanmoqda...
if not exist "%APPDATA%\AgentUmimiy" mkdir "%APPDATA%\AgentUmimiy"
if not exist "%APPDATA%\AgentUmimiy\agents.json" (
    copy /Y "packaging\agents.example.json" "%APPDATA%\AgentUmimiy\agents.json" >NUL
)
if not exist "litellm_config.yaml" (
    copy /Y "packaging\litellm_config.example.yaml" "litellm_config.yaml" >NUL
)
if not exist "%APPDATA%\AgentUmimiy\skills" mkdir "%APPDATA%\AgentUmimiy\skills"
robocopy "skills" "%APPDATA%\AgentUmimiy\skills" /E /XC /XN /XO >NUL

echo [4/4] RMS AI ishga tushirilmoqda...
start "" ".venv\Scripts\pythonw.exe" app.py
echo Tayyor!
