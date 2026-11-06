@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue CRM - Atualizar instalacao existente
py -3 update_windows.py
pause
