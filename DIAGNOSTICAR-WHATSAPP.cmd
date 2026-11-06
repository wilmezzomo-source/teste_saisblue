@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue - Diagnostico do WhatsApp oficial
py -3 diagnostico_whatsapp.py
pause
