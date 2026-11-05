@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue CRM - Rede e WhatsApp
py -3 configure_connections.py
pause
