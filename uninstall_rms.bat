@echo off
title RMS AI - O'chirish (Uninstall)
cd /d "%~dp0"

echo [1/3] Ishlayotgan RMS AI jarayonlari to'xtatilmoqda...
taskkill /F /IM RMSAI.exe >NUL 2>NUL
taskkill /F /IM RMSAIClient.exe >NUL 2>NUL

echo [2/3] Virtual muhit (.venv) o'chirilmoqda...
if exist ".venv" rmdir /S /Q ".venv"

echo [3/3] Foydalanuvchi ma'lumotlari (%APPDATA%\AgentUmimiy) haqida...
set /p DELDATA="Suhbatlar, sozlamalar va skillarni (%APPDATA%\AgentUmimiy) ham o'chiraymi? [y/N]: "
if /I "%DELDATA%"=="y" (
    if exist "%APPDATA%\AgentUmimiy" rmdir /S /Q "%APPDATA%\AgentUmimiy"
    if exist "%APPDATA%\AgentUmimiyClient" rmdir /S /Q "%APPDATA%\AgentUmimiyClient"
    echo Foydalanuvchi ma'lumotlari o'chirildi.
) else (
    echo Foydalanuvchi ma'lumotlari saqlab qolindi.
)

echo Tayyor! Loyiha papkasini endi bemalol o'chirishingiz mumkin.
pause
