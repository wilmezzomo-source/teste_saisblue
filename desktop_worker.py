"""Windows desktop updater engine. Uses the installation's existing Python only."""
import argparse
import base64
from contextlib import contextmanager
import ipaddress
import json
import ntpath
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

from update_windows import apply_update, restore_update, settings


class UpdateError(Exception):
    pass


def emit(message, **fields):
    print(json.dumps({'message': message, **fields}, ensure_ascii=False), flush=True)


def process_roles(snapshot, target):
    """Recognize only this installation; never stop processes by program name alone."""
    def canonical(value):
        if sys.platform=='win32' and ntpath.isabs(value):
            value=os.path.realpath(value)
        return ntpath.normcase(ntpath.normpath(value))
    root = canonical(str(target))
    roles = {}
    records = snapshot.get('processes', [])
    for p in records:
        if ntpath.basename(p.get('exe') or '').lower() not in ('python.exe','pythonw.exe'):
            continue
        command = p.get('command') or ''
        tokens = [a or b for a, b in re.findall(r'"([^"]*)"|([^\s]+)', command)]
        normalized = [canonical(t) for t in tokens]
        for script, role in [('launch.py','app'),('server.py','app'),('iniciar_https.py','https'),('setup_windows.py','wrapper')]:
            owned = ntpath.join(root, script) in normalized
            # A relative script is accepted only with a validated lifecycle marker, below.
            if owned and (script != 'launch.py' or 'serve' in tokens):
                roles[int(p['pid'])] = role
    controllers = {pid for pid, role in roles.items() if role == 'https'}
    servers = {pid for pid, role in roles.items() if role == 'app'}
    parents = {int(p['parent']) for p in records if int(p['pid']) in servers}
    for p in records:
        pid = int(p['pid'])
        if roles.get(pid) == 'wrapper' and pid not in parents:
            del roles[pid]
        if int(p.get('parent',0)) in controllers and ntpath.basename(p.get('exe') or '').lower() == 'ngrok.exe':
            command = (p.get('command') or '').lower()
            if 'http://127.0.0.1:3002' in command:
                roles[pid] = 'ngrok'
    for listener in snapshot.get('ports', []):
        allowed = ('app',) if int(listener['port']) == 3000 else ('https',)
        if roles.get(int(listener['pid'])) not in allowed:
            raise UpdateError('A porta do CRM está ocupada por um processo que não pude identificar com segurança. Use o aplicativo na conta Windows que iniciou o CRM; se necessário, abra como administrador.')
    return {int(p['pid']): (p, roles[int(p['pid'])]) for p in records if int(p['pid']) in roles}


def validate_target(target):
    target = Path(target).resolve()
    if str(target).startswith('\\\\'):
        raise UpdateError('Escolha a instalação em disco local do servidor.')
    for file in ('.env','server.py','launch.py','.venv/Scripts/python.exe'):
        p = target / file
        if not p.is_file() or p.is_symlink():
            raise UpdateError('Escolha a pasta original do CRM, onde ele já funciona.')
    values = settings(target / '.env')
    db = Path(values.get('CRM_DB') or target / 'data/crm.sqlite3')
    if not db.is_absolute(): db = target / db
    if not db.is_file():
        raise UpdateError('O banco da instalação não foi encontrado. Nenhum arquivo foi alterado.')
    return target, values


@contextmanager
def update_lock(target):
    runtime = Path(target) / '.runtime'
    runtime.mkdir(exist_ok=True)
    with (runtime / 'update.lock').open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1): handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateError('Já existe uma atualização em andamento nesta instalação.') from None
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class WindowsOps:
    def __init__(self, target, values):
        self.root, self.values = Path(target), values
        self.python = self.root / '.venv/Scripts/python.exe'
        host = values.get('CRM_LISTEN_HOST', '127.0.0.1')
        address = ipaddress.ip_address(host)
        if not (address.is_private or address.is_loopback):
            raise UpdateError('Endereço local do CRM inválido. A configuração foi preservada.')
        self.base = 'http://' + host + ':3000'
        self.transport = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.task_paused = False
        self.last_task_enabled = False
        self.root_aliases = [str(self.root)]
        if sys.platform=='win32':
            import ctypes
            buffer=ctypes.create_unicode_buffer(32768)
            if ctypes.windll.kernel32.GetShortPathNameW(str(self.root),buffer,len(buffer)):
                self.root_aliases.append(buffer.value)

    def encoded_roots(self):
        return base64.b64encode(json.dumps(self.root_aliases).encode()).decode()

    def powershell(self, code):
        encoded = base64.b64encode(code.encode('utf-16le')).decode('ascii')
        exe = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        r = subprocess.run([str(exe),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                           capture_output=True,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:
            raise UpdateError('O Windows não permitiu controlar o processo do CRM. Abra o atualizador na mesma conta que iniciou o CRM ou use Executar como administrador.')
        output = r.stdout.decode('utf-8-sig').strip()
        return json.loads(output) if output else None

    def snapshot(self):
        code = r'''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$roots=@([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('ROOT_B64'))|ConvertFrom-Json)
$all=@(Get-CimInstance Win32_Process)
$own=@($all | Where-Object {
 $match=$false
 foreach($root in $roots) {
  if($_.ExecutablePath -ieq (Join-Path $root '.venv\Scripts\python.exe') -or ($_.CommandLine -and $_.CommandLine.IndexOf($root,[StringComparison]::OrdinalIgnoreCase) -ge 0)) {$match=$true;break}
 }
 $_.Name -in @('python.exe','pythonw.exe') -and $match
})
$ids=@($own | ForEach-Object {$_.ProcessId})
$children=@($all | Where-Object { $_.Name -eq 'ngrok.exe' -and $_.ParentProcessId -in $ids })
$rows=@(@($own)+@($children) | ForEach-Object { @{pid=[int]$_.ProcessId;parent=[int]$_.ParentProcessId;exe=$_.ExecutablePath;command=$_.CommandLine;started=$_.CreationDate.ToUniversalTime().ToString('o')} })
$ports=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -in @(3000,3002)} | ForEach-Object {@{pid=[int]$_.OwningProcess;port=[int]$_.LocalPort}})
@{processes=$rows;ports=$ports}|ConvertTo-Json -Depth 5 -Compress'''.replace('ROOT_B64',self.encoded_roots())
        return self.powershell(code)

    def task(self, action):
        # Touch only the exact named application task pointing at this project's script.
        result = self.powershell(r'''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$roots=@([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('ROOT_B64'))|ConvertFrom-Json)
$task=Get-ScheduledTask -TaskName 'SaisBlueCRM' -ErrorAction SilentlyContinue
$match=$false
foreach($root in $roots) {
 if($task -and @($task.Actions | Where-Object { $_.Arguments -and $_.Arguments.IndexOf((Join-Path $root 'deploy\windows.ps1'),[StringComparison]::OrdinalIgnoreCase) -ge 0 }).Count -gt 0) {$match=$true;break}
}
$enabled=$match -and $task.Settings.Enabled
if($match) { ACTION }
@{matched=[bool]$match;enabled=[bool]$enabled}|ConvertTo-Json -Compress'''.replace('ROOT_B64',self.encoded_roots()).replace('ACTION',action))
        self.last_task_enabled=result['enabled']
        return result['matched']

    def kill(self, record):
        encoded = base64.b64encode(json.dumps(record).encode()).decode()
        self.powershell('''$ErrorActionPreference='Stop'
$expected=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('RECORD'))|ConvertFrom-Json
$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+[int]$expected.pid)
if($p) {
 if($p.CreationDate.ToUniversalTime().ToString('o') -ne $expected.started -or $p.CommandLine -cne $expected.command -or $p.ExecutablePath -ine $expected.exe) { throw 'Identidade do processo mudou' }
 Stop-Process -Id ([int]$expected.pid) -ErrorAction Stop
}'''.replace('RECORD',encoded))

    def stop(self):
        owned = process_roles(self.snapshot(), str(self.root))
        # Disable restart while replacing files, only for this installation's own task.
        matched=self.task("if($task.Settings.Enabled){Disable-ScheduledTask -TaskName 'SaisBlueCRM'|Out-Null}; if($task.State -eq 'Running'){Stop-ScheduledTask -TaskName 'SaisBlueCRM' -ErrorAction Stop}")
        self.task_paused = self.task_paused or (matched and self.last_task_enabled)
        for role in ('https','app'):
            state = self.root / '.runtime' / (role+'.json')
            try:
                marker = json.loads(state.read_text(encoding='utf-8'))
                if int(marker['pid']) in owned and owned[int(marker['pid'])][1] == role:
                    (state.with_suffix('.stop')).write_text('update',encoding='ascii')
            except (OSError, ValueError, KeyError):
                pass
        if owned:
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                alive=process_roles(self.snapshot(),str(self.root))
                if not any(role in ('app','https','ngrok') for _,role in alive.values()):break
                time.sleep(.3)
            # Revalidate exact PID, creation time, executable and argv before any stop.
            for record,role in sorted(owned.values(),key=lambda pair: {'ngrok':0,'https':1,'app':2,'wrapper':3}[pair[1]]):
                self.kill(record)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            snapshot=self.snapshot()
            process_roles(snapshot,str(self.root))
            if not snapshot['ports']:return
            time.sleep(.3)
        raise UpdateError('O CRM ainda não encerrou. A atualização foi interrompida antes de substituir arquivos.')

    def command(self, args, timeout=60):
        return subprocess.run([str(self.python),*map(str,args)],cwd=self.root,capture_output=True,
                              timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0

    def validate(self):
        if not self.command([self.root/'launch.py','--config',self.root/'.env','check']):
            raise UpdateError('A nova versão não passou na conferência do banco e da aplicação.')

    def health(self, version=None):
        try:
            with self.transport.open(self.base+'/healthz',timeout=2) as response:
                info=json.load(response)
            return info.get('ok') is True and info.get('application') == 'sais-blue-crm' and (not version or info.get('version')==version)
        except (OSError, ValueError):
            return False

    def spawn(self, script, args, role):
        folder=self.root/'.runtime';folder.mkdir(exist_ok=True)
        with (folder/(role+'.log')).open('ab') as log:
            return subprocess.Popen([str(self.python),str(self.root/script),*map(str,args)],cwd=self.root,
                                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)

    def start(self, version=None):
        if not self.health(version):
            if self.task_paused:
                self.task("Enable-ScheduledTask -TaskName 'SaisBlueCRM'|Out-Null; Start-ScheduledTask -TaskName 'SaisBlueCRM'")
                self.task_paused=False
            else:
                self.spawn('launch.py',['--config',self.root/'.env','serve'],'app')
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                if self.health(version):break
                time.sleep(.3)
            else:
                raise UpdateError('A aplicação não confirmou a inicialização. Vou recuperar a versão anterior.')
        return self.connection()

    def connection(self):
        if not self.values.get('NGROK_AUTHTOKEN'):
            return True  # A separately managed HTTPS proxy is left untouched.
        state=self.root/'.runtime/https.json'
        owned=process_roles(self.snapshot(),str(self.root))
        existing=any(role=='https' for _,role in owned.values())
        try:
            marker=json.loads(state.read_text(encoding='utf-8'))
            if marker.get('status')=='ready' and marker.get('pid') in owned and owned[marker['pid']][1]=='https':
                return True
        except (OSError,ValueError,KeyError):
            pass
        if existing and not state.is_file():
            # The first migration can encounter the older controller without lifecycle files.
            from public_webhook_check import verify_public
            try:
                verify_public(self.values.get('META_WEBHOOK_URL',''),self.values.get('META_VERIFY_TOKEN',''))
                return True
            except (ValueError,OSError):return False
        process=None if existing else self.spawn('iniciar_https.py',[],'https')
        deadline=time.monotonic()+75
        while time.monotonic()<deadline:
            if process is not None and process.poll() is not None:return False
            try:
                marker=json.loads(state.read_text(encoding='utf-8'))
                if marker.get('status')=='ready':
                    current=process_roles(self.snapshot(),str(self.root))
                    if marker.get('pid') in current and current[marker['pid']][1]=='https':
                        return marker.get('callback')==self.values.get('META_WEBHOOK_URL') or not self.values.get('META_WEBHOOK_URL')
                if marker.get('status')=='stopped' and existing:return False
            except (OSError,ValueError):pass
            time.sleep(.4)
        return False


def update_installation(source,target,ops,report=emit,install=True):
    """Package is already downloaded/verified by the GUI. Stop -> backup -> validate -> start."""
    source,target=Path(source).resolve(),Path(target).resolve()
    for name in ('server.py','launch.py','qualification.py','runtime_control.py','public/index.html'):
        if not (source/name).is_file():
            raise UpdateError('O pacote baixado está incompleto. O CRM não foi interrompido.')
    match=re.search(r"^RELEASE = '([0-9.]+)'$",(source/'server.py').read_text(encoding='utf-8'),re.M)
    if not match:raise UpdateError('Não consegui conferir a versão do pacote. O CRM não foi interrompido.')
    version=match[1]
    backup=None
    stopped=False
    def remember(path):
        nonlocal backup
        backup=path
        report('Backup concluído. Aplicando os arquivos.',progress=60)
    try:
        report('Encerrando somente o CRM e sua conexão WhatsApp.',progress=40)
        ops.stop()
        stopped=True
        report('Criando backup do banco e da versão anterior.',progress=50)
        apply_update(source,target,install=install,on_backup=remember)
        report('Conferindo a nova versão e preservação do banco.',progress=75)
        ops.validate()
        report('Iniciando o CRM e verificando a conexão HTTPS.',progress=85)
        connected=ops.start(version)
        report('CRM atualizado e aberto. A conexão HTTPS está pronta.' if connected else 'CRM atualizado. Clique em Iniciar / reconectar para tentar restabelecer a conexão WhatsApp.',
               event='done',progress=100,version=version,connection_ready=connected)
        return {'version':version,'connection_ready':connected,'backup':str(backup)}
    except Exception as error:
        if backup:
            report('A atualização falhou. Recuperando a versão anterior.',progress=85)
            try:
                ops.stop()
                restore_update(backup,target)
                ops.validate()
                connected=ops.start()
            except Exception:
                raise UpdateError('A atualização foi interrompida. Há um backup na pasta backups; a recuperação automática não foi confirmada. Os arquivos .env e .venv foram preservados.') from None
            raise UpdateError('A atualização falhou; a versão anterior foi recuperada e o CRM reiniciado.'+(' A conexão HTTPS precisa ser reconectada.' if not connected else '')) from None
        # A failure before copying must still re-enable an application task we paused.
        if stopped or getattr(ops,'task_paused',False):
            try:ops.start()
            except Exception:pass
        if isinstance(error,UpdateError):raise
        raise UpdateError('Não foi possível concluir a preparação. Nenhum arquivo da aplicação foi substituído.') from None


def main():
    if sys.platform!='win32':raise UpdateError('Execute este aplicativo no servidor Windows.')
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',required=True)
    parser.add_argument('--source')
    parser.add_argument('--action',choices=('update','start','stop'),default='update')
    args=parser.parse_args()
    target,values=validate_target(args.target)
    ops=WindowsOps(target,values)
    with update_lock(target):
        if args.action=='update':
            if not args.source:raise UpdateError('Pacote da atualização ausente.')
            update_installation(args.source,target,ops)
        elif args.action=='stop':
            ops.stop();emit('CRM e conexão HTTPS encerrados.',event='done',progress=100)
        else:
            emit('Iniciando o CRM e a conexão HTTPS.',progress=50)
            connected=ops.start()
            emit('CRM iniciado. Conexão HTTPS pronta.' if connected else 'CRM iniciado. A conexão HTTPS precisa ser reconectada.',event='done',connection_ready=connected,progress=100)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:main()
    except UpdateError as exc:
        emit(str(exc),event='error');sys.exit(1)
    except Exception:
        emit('A operação não foi concluída. Banco, configuração e senhas não foram exibidos. Confira se selecionou a instalação original e se tem permissão no Windows.',event='error');sys.exit(1)
