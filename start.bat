@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python topilmadi. python.org dan Python 3.13 ni o'rnating ^(Add python.exe to PATH belgilang^).
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Birinchi marta: kutubxonalar o'rnatilmoqda, biroz kuting...
  py -3.13 -m venv .venv || py -3 -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

if "%BOT_TOKEN%"=="" set /p BOT_TOKEN=Bot tokenini yozing va Enter bosing: 
if "%ANTHROPIC_API_KEY%"=="" set /p ANTHROPIC_API_KEY=Anthropic kaliti (bo'lmasa bo'sh qoldirib Enter bosing): 

echo Bot ishga tushdi. Oynani yopmang.
".venv\Scripts\python.exe" -m bot.main
pause
