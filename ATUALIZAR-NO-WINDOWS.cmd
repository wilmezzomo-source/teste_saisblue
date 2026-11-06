@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sais Blue CRM - Atualizar instalacao existente
set "SAISBLUE_RELEASE_ROOT=%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $crmDialog = New-Object System.Windows.Forms.FolderBrowserDialog; $crmDialog.Description = 'Selecione a pasta ANTIGA do CRM ja instalado'; if ($crmDialog.ShowDialog() -ne 'OK') { exit 0 }; $crmPython = Join-Path $crmDialog.SelectedPath '.venv\Scripts\python.exe'; if (!(Test-Path -LiteralPath $crmPython)) { Write-Host 'Nao encontrei o Python nessa pasta. Selecione a pasta original do CRM.'; exit 1 }; $crmUpdater = Join-Path $env:SAISBLUE_RELEASE_ROOT 'update_windows.py'; & $crmPython $crmUpdater --target $crmDialog.SelectedPath; exit $LASTEXITCODE"
pause
