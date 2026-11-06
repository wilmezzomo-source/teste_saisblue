@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue - Receber WhatsApp por HTTPS
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Execute este arquivo na pasta ORIGINAL do CRM que ja funciona.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0iniciar_https.py"
pause
