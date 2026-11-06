@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue CRM - Preparacao do Windows
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0setup_windows.py"
  pause
  exit /b
)
where py >nul 2>nul
if errorlevel 1 (
  echo Precisamos do Python 3.12 ou superior com o launcher py.
  echo Instale pelo site oficial https://www.python.org/downloads/windows/
  echo Marque a opcao de instalar o launcher e execute este arquivo novamente.
  pause
  exit /b 1
)
py -3 setup_windows.py
if errorlevel 1 (
  echo.
  echo A preparacao nao foi concluida. Guarde a mensagem acima para o responsavel de TI.
  pause
  exit /b 1
)
pause
