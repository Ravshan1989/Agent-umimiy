@echo off
title Agent Umimiy - Barcha Xizmatlarni Ishga Tushirish
echo [1/3] Ollama tekshirilmoqda...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    start "" /B "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
)

echo [2/3] FreeLLMAPI lokal shlyuzi ishga tushirilmoqda (port 3001)...
netstat -ano | findstr ":3001 " >NUL
if "%ERRORLEVEL%"=="1" (
    start "" /B /D "D:\llm\freellm" node server\dist\index.js
)

echo [3/3] Agent Umimiy desktop oynasi ochilmoqda...
start "" /D "D:\agent" "D:\llm\.venv\Scripts\pythonw.exe" "D:\agent\app.py"
echo Tayyor!
