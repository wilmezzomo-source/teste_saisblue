@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue - Validar instalacao
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Nao encontrei o Python do CRM nesta pasta.
  echo Execute este arquivo na pasta ORIGINAL em que o CRM ja funciona.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0validar_instalacao.py"
pause
