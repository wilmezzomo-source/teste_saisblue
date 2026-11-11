"""Single Windows batch-session supervisor; does not send customer messages."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

from automatic_start import is_enabled, write_state
from desktop_worker import WindowsOps, UpdateError, process_roles, update_lock, validate_target

ROOT=Path(__file__).resolve().parent


class Supervisor:
    def __init__(self, ops, clock=time.time):
        self.ops,self.clock=ops,clock
        self.next={'app':0,'https':0}
        self.failures={'app':0,'https':0}
        self.unhealthy=0
        self.started={'app':clock(),'https':clock()}

    def state(self, status, **extra):
        write_state(self.ops.root,'supervisor',{'status':status,'updated':self.clock(),**extra})

    def attempt(self, role):
        now=self.clock()
        if now<self.next[role]:return False
        self.failures[role]+=1
        delay=min(300,15*2**min(5,self.failures[role]-1))
        self.next[role]=now+delay
        self.started[role]=now
        script,args=('launch.py',['--config',self.ops.root/'.env','serve']) if role=='app' else ('iniciar_https.py',[])
        self.ops.spawn(script,args,role)
        return True

    def cycle(self):
        # The updater holds this same lock for the entire stop/backup/rollback.
        with update_lock(self.ops.root):
            if not is_enabled(self.ops.root):
                self.state('paused',message='Parado pelo aplicativo. Use Iniciar / reconectar para retomar.')
                return
            self.ops.reload()
            snapshot=self.ops.snapshot()
            owned=process_roles(snapshot,str(self.ops.root))
            roles={role for _,role in owned.values()}
            if not self.ops.health():
                self.unhealthy+=1
                if 'app' in roles:
                    # Allow slow startup and tolerate two missed checks; never
                    # terminate a listener whose installation identity is unknown.
                    if self.unhealthy<3 or self.clock()-self.started['app']<60:
                        self.state('crm_starting');return
                    self.ops.stop()
                    self.started['https']=self.clock()
                self.attempt('app')
                self.state('crm_reconnecting',retry_at=self.next['app'])
                return
            self.unhealthy=0
            self.failures['app']=0
            self.next['app']=0
            if not self.ops.values.get('NGROK_AUTHTOKEN'):
                self.state('running',connection='managed_separately');return
            if 'https' not in roles:
                # The ngrok parent can die before its child. Do not launch a
                # second tunnel when port 3002 has an unidentified owner.
                if self.clock()>=self.next['https']:
                    for record,role in owned.values():
                        if role=='ngrok':self.ops.kill(record)
                self.attempt('https')
                self.state('https_reconnecting',retry_at=self.next['https']);return
            try:
                marker=json.loads((self.ops.root/'.runtime/https.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):marker={}
            controller=marker.get('pid') in owned and owned[marker['pid']][1]=='https'
            if controller and marker.get('status')=='ready' and 'ngrok' in roles:
                self.failures['https']=0
                self.next['https']=0
                self.started['https']=self.clock()
                self.state('running',connection='ready');return
            # The controller checks its child, local tunnel and public challenge,
            # then exits on persistent failure; do not race its recovery checks.
            if self.clock()-self.started['https']>120:
                for record,role in sorted(owned.values(),key=lambda pair: 0 if pair[1]=='ngrok' else 1):
                    if role in ('ngrok','https'):self.ops.kill(record)
                self.state('https_reconnecting')
            else:self.state('https_checking')


def code_signature(root):
    digest=hashlib.sha256()
    for name in ('supervise_crm.py','automatic_start.py','desktop_worker.py','runtime_control.py'):
        digest.update((Path(root)/name).read_bytes())
    return digest.digest()


def run(root=ROOT, stop=None, poll_interval=30):
    stop=stop or threading.Event()
    root,values=validate_target(root)
    with update_lock(root,'supervisor'):
        supervisor=Supervisor(WindowsOps(root,values))
        signature=code_signature(root)
        supervisor.state('starting')
        # Keep an operating Windows server awake. This does not prevent manual
        # shutdown/sleep and is automatically cleared when this process exits.
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        while not stop.is_set():
            try:
                with update_lock(root):
                    if code_signature(root)!=signature:
                        supervisor.state('reloading');return 75
                supervisor.cycle()
            except UpdateError:
                supervisor.state('waiting',message='Aguardando atualização ou conferência do processo desta instalação.')
            except Exception:
                supervisor.state('retrying',message='Falha na verificação local; nova tentativa automática em 30 segundos.')
            stop.wait(poll_interval)
    return 0


if __name__=='__main__':
    if sys.platform!='win32':sys.exit(1)
    try:sys.exit(run())
    except Exception:sys.exit(1)  # Task Scheduler restarts a failed supervisor.
