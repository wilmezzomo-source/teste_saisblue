"""Install a limited, passwordless Windows boot task for this installation only."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent


def write_state(root, name, state):
    folder=Path(root)/'.runtime'
    folder.mkdir(exist_ok=True)
    path=folder/(name+'.json')
    temp=folder/(name+'.'+str(os.getpid())+'.tmp')
    temp.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
    os.replace(temp,path)


def set_enabled(root, enabled):
    write_state(root,'automatic-control',{'enabled':bool(enabled)})


def is_enabled(root):
    path=Path(root)/'.runtime/automatic-control.json'
    if not path.exists():return True
    try:return json.loads(path.read_text(encoding='utf-8')).get('enabled') is True
    except (OSError,ValueError):return False  # Do not ignore a damaged manual-stop record.


def task_identity(root):
    root=Path(root).resolve()
    suffix=hashlib.sha256(str(root).lower().encode()).hexdigest()[:12]
    return 'SaisBlueCRM-Automatico-'+suffix, str(root/'.venv/Scripts/python.exe'), subprocess.list2cmdline([str(root/'supervise_crm.py')])


def task_prelude(root):
    from configure_connections import ps_literal
    name,python,args=task_identity(root)
    return f'''$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$name={ps_literal(name)}; $python={ps_literal(python)}; $crmArgs={ps_literal(args)}
$task=Get-ScheduledTask -TaskPath '\\' -TaskName $name -ErrorAction SilentlyContinue
$match=$task -and @($task.Actions).Count -eq 1 -and $task.Actions[0].Execute -ieq $python -and $task.Actions[0].Arguments -ceq $crmArgs
'''


def task_status(ops):
    try:
        return ops.powershell(task_prelude(ops.root)+'''@{enabled=[bool]($match -and $task.Settings.Enabled -and $task.Principal.LogonType -eq 'S4U' -and $task.Principal.RunLevel -eq 'Limited');running=[bool]($match -and $task.State -eq 'Running')}|ConvertTo-Json -Compress''')
    except Exception:return {'enabled':False,'running':False}


def ensure_automatic(ops):
    """Called by the worker, including when the user still has the older GUI."""
    from configure_connections import ps_literal
    status=task_status(ops)
    if status.get('enabled'):
        if not status.get('running'):
            try:
                ops.powershell(task_prelude(ops.root)+"if($match){Start-ScheduledTask -TaskName $name}")
            except Exception:return False
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                state=json.loads((ops.root/'.runtime/supervisor.json').read_text(encoding='utf-8'))
                if time.time()-state.get('updated',0)<90 and task_status(ops).get('running',False):return True
            except (OSError,ValueError):pass
            time.sleep(1)
        return False
    try:
        identity=ops.powershell("@{sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value}|ConvertTo-Json -Compress")
        args=subprocess.list2cmdline([str(ops.root/'automatic_start.py'),'--target',str(ops.root),'--owner-sid',identity['sid']])
        # Windows requires local administrator consent to register a boot task.
        # The task itself runs as the original user with LIMITED rights (S4U),
        # without storing a password and without requiring an interactive login.
        result=ops.powershell(f'''$ErrorActionPreference='Stop'
$p=Start-Process -FilePath {ps_literal(ops.python)} -ArgumentList {ps_literal(args)} -WorkingDirectory {ps_literal(ops.root)} -Verb RunAs -WindowStyle Hidden -PassThru
if(!$p.WaitForExit(90000)){{throw 'O Windows ainda não confirmou a instalação.'}}
@{{ok=($p.ExitCode -eq 0)}}|ConvertTo-Json -Compress''',timeout=150)
        return bool(result.get('ok') and task_status(ops).get('enabled'))
    except Exception:return False


def install(ops, owner_sid):
    from configure_connections import ps_literal
    if not re.fullmatch(r'S-1-5-21-(?:\d+-){2}\d+-\d+',owner_sid):
        raise ValueError('Conta Windows inválida para o início automático.')
    # Store execution aliases need an interactive session. Stage the actual agent
    # while in the installing user's context, before registering a batch task.
    if ops.values.get('NGROK_AUTHTOKEN'):
        from iniciar_https import prepare_background_ngrok
        prepare_background_ngrok(ops.root)
    code=task_prelude(ops.root)+f'''
if($task -and !$match) {{throw 'Já existe uma tarefa diferente com este nome.'}}
$sid=[Security.Principal.SecurityIdentifier]::new({ps_literal(owner_sid)})
$account=$sid.Translate([Security.Principal.NTAccount]).Value
# Files created in an elevated C:\ installation can otherwise be writable only
# through the Administrators group, which a LIMITED task cannot use. Grant only
# the original operator access to this installation; do not change other ACLs.
& icacls {ps_literal(ops.root)} /grant ('*'+$sid.Value+':(OI)(CI)M') | Out-Null
if($LASTEXITCODE -ne 0) {{throw 'Não foi possível permitir o acesso da conta à instalação.'}}
$action=New-ScheduledTaskAction -Execute $python -Argument $crmArgs -WorkingDirectory {ps_literal(ops.root)}
$principal=New-ScheduledTaskPrincipal -UserId $account -LogonType S4U -RunLevel Limited
$triggers=@((New-ScheduledTaskTrigger -AtStartup),(New-ScheduledTaskTrigger -AtLogOn -User $account))
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Trigger $triggers -Settings $settings -Force|Out-Null
Start-ScheduledTask -TaskName $name
@{{installed=$true}}|ConvertTo-Json -Compress
'''
    ops.powershell(code)
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            state=json.loads((ops.root/'.runtime/supervisor.json').read_text(encoding='utf-8'))
            if time.time()-state.get('updated',0)<20 and task_status(ops).get('running'):
                write_state(ops.root,'automatic-install',{'ok':True,'task':task_identity(ops.root)[0]})
                return
        except (OSError,ValueError):pass
        time.sleep(1)
    raise ValueError('A tarefa foi registrada, mas o monitor não confirmou a inicialização. Use Iniciar / reconectar novamente.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',default=str(ROOT))
    parser.add_argument('--owner-sid',required=True)
    args=parser.parse_args()
    if sys.platform!='win32':raise ValueError('Execute no servidor Windows.')
    root=Path(args.target).resolve()
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():raise ValueError('O Windows precisa autorizar o registro do início automático.')
        from desktop_worker import WindowsOps, validate_target
        root,values=validate_target(root)
        install(WindowsOps(root,values),args.owner_sid)
    except Exception:
        write_state(root,'automatic-install',{'ok':False,'message':'O Windows não confirmou o início automático. O CRM continua disponível pelo aplicativo; tente Iniciar / reconectar ou solicite à TI a permissão de tarefa em segundo plano.'})
        sys.exit(1)


if __name__=='__main__':main()
