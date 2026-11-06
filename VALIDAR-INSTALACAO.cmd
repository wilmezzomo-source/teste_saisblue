@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue - Validar instalacao
py -3 validar_instalacao.py
pause
