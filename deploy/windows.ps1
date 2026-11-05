param(
    [ValidateSet('Install','Check','Run','Admin','Backup','Proxy','RegisterTasks')]
    [string]$Action = 'Check',
    [string]$Email,
    [string]$Name,
    [string]$CaddyPath
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$PythonPath = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ConfigPath = Join-Path $ProjectRoot '.env'
Set-Location $ProjectRoot
function Assert-Success {
    if ($LASTEXITCODE -ne 0) { throw "O comando falhou (codigo $LASTEXITCODE)." }
}
function Import-Config {
    if (!(Test-Path $ConfigPath)) { throw 'Configure o arquivo .env primeiro.' }
    foreach ($Line in (Get-Content -LiteralPath $ConfigPath)) {
        if (!$Line.Trim() -or $Line.TrimStart().StartsWith('#')) { continue }
        $Parts = $Line.Split('=', 2)
        if ($Parts.Count -ne 2) { throw 'Linha invalida em .env.' }
        $Key = $Parts[0].Trim()
        if ($Key -notin @('APP_ENV','APP_URL','CRM_DB','ALLOW_SIMULATION','META_APP_SECRET','META_VERIFY_TOKEN','META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_API_VERSION','CRM_DOMAIN')) { throw 'Chave desconhecida em .env.' }
        [Environment]::SetEnvironmentVariable($Key, $Parts[1].Trim(), 'Process')
    }
}
switch ($Action) {
    'Install' {
        & py -3 -m venv (Join-Path $ProjectRoot '.venv')
        Assert-Success
        & $PythonPath -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
        Assert-Success
        New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'data'),(Join-Path $ProjectRoot 'backups') | Out-Null
        if (!(Test-Path $ConfigPath)) { Copy-Item (Join-Path $ProjectRoot '.env.example') $ConfigPath }
        Write-Output 'Dependencias instaladas. Configure .env e depois execute Check e Admin.'
    }
    'Check' { & $PythonPath (Join-Path $ProjectRoot 'launch.py') --config $ConfigPath check; Assert-Success }
    'Run' { & $PythonPath (Join-Path $ProjectRoot 'launch.py') --config $ConfigPath serve; Assert-Success }
    'Admin' {
        if (!$Email -or !$Name) { throw 'Informe -Email e -Name. A senha sera solicitada no terminal.' }
        & $PythonPath (Join-Path $ProjectRoot 'launch.py') --config $ConfigPath admin --email $Email --name $Name
        Assert-Success
    }
    'Backup' {
        $BackupDirectory = Join-Path $ProjectRoot 'backups'
        New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
        $Destination = Join-Path $BackupDirectory (('crm-{0}.sqlite3' -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
        & $PythonPath (Join-Path $ProjectRoot 'launch.py') --config $ConfigPath backup --destination $Destination
        Assert-Success
        # Retention only for backups generated here. Keep a separate encrypted/off-server copy.
        Get-ChildItem -LiteralPath $BackupDirectory -Filter 'crm-*.sqlite3' | Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item
    }
    'Proxy' {
        Import-Config
        if (!$CaddyPath -or !(Test-Path $CaddyPath)) { throw 'Informe -CaddyPath com o caminho do caddy.exe.' }
        & $CaddyPath run --config (Join-Path $PSScriptRoot 'Caddyfile') --adapter caddyfile
        Assert-Success
    }
    'RegisterTasks' {
        if (!$CaddyPath -or !(Test-Path $CaddyPath)) { throw 'Instale Caddy e informe -CaddyPath antes de registrar as tarefas.' }
        # Run in an elevated terminal after network/DNS and the application are validated.
        $Sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        & icacls $ProjectRoot /inheritance:r /grant:r "*${Sid}:(OI)(CI)F" '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'
        Assert-Success
        & icacls (Join-Path $ProjectRoot 'data') /grant '*S-1-5-19:(OI)(CI)M'
        Assert-Success
        & icacls (Join-Path $ProjectRoot 'backups') /grant '*S-1-5-19:(OI)(CI)M'
        Assert-Success
        $Principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\LOCAL SERVICE' -LogonType ServiceAccount
        $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
        $Script = $PSCommandPath
        $Run = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -File `"$Script`" -Action Run" -WorkingDirectory $ProjectRoot
        $Proxy = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -File `"$Script`" -Action Proxy -CaddyPath `"$CaddyPath`"" -WorkingDirectory $ProjectRoot
        $Backup = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -File `"$Script`" -Action Backup" -WorkingDirectory $ProjectRoot
        Register-ScheduledTask -TaskName 'SaisBlueCRM' -Action $Run -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $Principal -Settings $Settings -Force | Out-Null
        Register-ScheduledTask -TaskName 'SaisBlueCRM-HTTPS' -Action $Proxy -Trigger (New-ScheduledTaskTrigger -AtStartup) -Principal $Principal -Settings $Settings -Force | Out-Null
        Register-ScheduledTask -TaskName 'SaisBlueCRM-Backup' -Action $Backup -Trigger (New-ScheduledTaskTrigger -Daily -At '02:00') -Principal $Principal -Settings $Settings -Force | Out-Null
        Start-ScheduledTask -TaskName 'SaisBlueCRM'
        Start-ScheduledTask -TaskName 'SaisBlueCRM-HTTPS'
        Write-Output 'Tarefas registradas. Valide HTTPS, login, reinicio do Windows e backup antes de operar.'
    }
}
