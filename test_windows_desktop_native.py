from sqlite_context import connection as sqlite_connection
"""Runs on an isolated Windows CI host, never against a company installation."""
import json
import base64
import ctypes
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


@unittest.skipUnless(sys.platform=='win32' and os.environ.get('SAISBLUE_NATIVE_WINDOWS_TEST')=='1','Isolated Windows runner required')
class WindowsDesktopNativeTest(unittest.TestCase):
    def test_real_gui_detects_running_installation_and_stops_only_its_crm(self):
        from desktop_worker import WindowsOps
        class DiagnosticOps(WindowsOps):
            def powershell(self,code):
                encoded=base64.b64encode(code.encode('utf-16le')).decode('ascii')
                exe=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
                result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:
                    details=(result.stderr.decode('utf-8',errors='replace')+' '+result.stdout.decode('utf-8',errors='replace'))[:4000]
                    # Isolated fixture only: no Meta/ngrok credentials or company data exist here.
                    print('::error title=Windows fixture diagnostic::'+details.replace('%','%25').replace('\r','%0D').replace('\n','%0A'),flush=True)
                    raise AssertionError('Windows fixture PowerShell failed: '+details)
                value=result.stdout.decode('utf-8-sig').strip()
                return json.loads(value) if value else None
        with tempfile.TemporaryDirectory(prefix='SaisBlue CRM test ') as folder:
            root=Path(folder).resolve()
            subprocess.run([sys.executable,'-m','venv','--without-pip','--system-site-packages',root/'.venv'],check=True,capture_output=True)
            (root/'data').mkdir()
            (root/'server.py').write_text("RELEASE = '2026.11.06.0'\n",encoding='utf-8')
            (root/'INICIAR-NO-WINDOWS.cmd').write_text('fixture')
            repo=Path(__file__).parent
            (root/'requirements.txt').write_bytes((repo/'requirements.txt').read_bytes())
            for file in ('desktop_worker.py','update_windows.py','sqlite_context.py'):
                shutil.copyfile(repo/file,root/file)
            config='APP_ENV=development\nAPP_URL=http://127.0.0.1:3000\nCRM_LISTEN_HOST=127.0.0.1\nCRM_DB=data/crm.sqlite3\nALLOW_SIMULATION=0\nMETA_APP_SECRET=\nMETA_VERIFY_TOKEN=\nMETA_ACCESS_TOKEN=\nMETA_PHONE_NUMBER_ID=\n'
            (root/'.env').write_text(config,encoding='utf-8')
            from server import create_app,database
            app=create_app({'DATABASE':str(root/'data/crm.sqlite3')})
            with database(app) as db:
                db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated) VALUES('fixture','Preserved customer','5511999991234','Novo contato','Fixture',1,1)")
            (root/'launch.py').write_text('''from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'{"ok":true,"application":"sais-blue-crm","version":"2026.11.06.0"}')
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',3000),Handler).serve_forever()
''',encoding='utf-8')
            python=root/'.venv/Scripts/python.exe'
            buffer=ctypes.create_unicode_buffer(32768)
            short=root
            if ctypes.windll.kernel32.GetShortPathNameW(str(root),buffer,len(buffer)):short=Path(buffer.value)
            crm=subprocess.Popen([str(python),str(short/'launch.py'),'serve'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            other=subprocess.Popen([sys.executable,'-c','import time;time.sleep(180)'])
            ops=DiagnosticOps(root,{'CRM_LISTEN_HOST':'127.0.0.1'})
            try:
                for _ in range(50):
                    if ops.health('2026.11.06.0'):break
                    time.sleep(.2)
                self.assertTrue(ops.health('2026.11.06.0'))
                # Start the delivered GUI: staging means the original launcher exits.
                encoded_root=str(root).replace("'","''")
                do_update=(repo/'windows-release.json').is_file()
                release_version=json.loads((repo/'windows-release.json').read_text())['version'] if do_update else None
                action='Atualizar e abrir CRM' if do_update else 'Parar CRM'
                subprocess.Popen([str(repo/'desktop/SaisBlue-Atualizador.exe'),'--action','update' if do_update else 'stop'])
                code=r'''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class SaisBlueGui {
 delegate bool Callback(IntPtr handle, IntPtr data);
 [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, Callback callback, IntPtr data);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h,int m,IntPtr w,StringBuilder l);
 [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h,int m,IntPtr w,IntPtr l);
 public static List<IntPtr> Children(IntPtr parent) { var list=new List<IntPtr>(); EnumChildWindows(parent,(h,d)=>{list.Add(h);return true;},IntPtr.Zero);return list; }
 public static string Text(IntPtr h) { var b=new StringBuilder(32768);SendMessage(h,13,(IntPtr)b.Capacity,b);return b.ToString(); }
 [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr h);
 [DllImport("user32.dll")] static extern int GetDlgCtrlID(IntPtr h);
 public static void Click(IntPtr h) { SendMessage(GetParent(h),273,(IntPtr)GetDlgCtrlID(h),h); }
}
'@
$deadline=(Get-Date).AddSeconds(20);$window=$null
while((Get-Date) -lt $deadline) {
 $ps=@(Get-Process -Name 'SaisBlue-Atualizador' -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -eq 'Sais Blue CRM'})
 if($ps.Count -eq 1) {$window=$ps[0].MainWindowHandle;break}
 Start-Sleep -Milliseconds 200
}
if(!$window) {throw 'Updater window did not open'}
$found=$false;$button=[IntPtr]::Zero;$ready=(Get-Date).AddSeconds(8)
while((Get-Date) -lt $ready -and (!$found -or $button -eq [IntPtr]::Zero)) {
 foreach($handle in [SaisBlueGui]::Children($window)) {
  $value=[SaisBlueGui]::Text($handle)
  if($value -eq 'TARGET_ROOT') {$found=$true}
  if($value -eq 'BUTTON_ACTION') {$button=$handle}
 }
 if(!$found -or $button -eq [IntPtr]::Zero){Start-Sleep -Milliseconds 200}
}
if(!$found -or $button -eq [IntPtr]::Zero) {
 $controls=@([SaisBlueGui]::Children($window)|ForEach-Object {[SaisBlueGui]::Text($_)}) -join '; '
 throw ('Native GUI controls missing; expected TARGET_ROOT and BUTTON_ACTION; found: '+$controls)
}
@{window=$true;detected=$found;pid=$ps[0].Id}|ConvertTo-Json -Compress'''.replace('TARGET_ROOT',encoded_root).replace('BUTTON_ACTION',action)
                result=ops.powershell(code)
                self.assertTrue(result['detected'])
                deadline=time.monotonic()+(120 if do_update else 45)
                if do_update:
                    while time.monotonic()<deadline:
                        if ops.health(release_version):break
                        time.sleep(.5)
                    if not ops.health(release_version):
                        # These values come only from this isolated CI fixture, never company data.
                        try:
                            with urllib.request.urlopen('http://127.0.0.1:3000/healthz',timeout=3) as response:
                                actual=json.loads(response.read(4096))
                        except Exception as exc:
                            actual={'unavailable':type(exc).__name__}
                        print('::error title=Expected and running fixture versions::'+json.dumps({'expected':release_version,'actual':actual}),flush=True)
                        diagnostic=code.split('$deadline=')[0]+"\n$p=Get-Process -Id "+str(result['pid'])+" -ErrorAction SilentlyContinue; $text=if($p){@([SaisBlueGui]::Children($p.MainWindowHandle)|ForEach-Object {[SaisBlueGui]::Text($_)}) -join '; '}else{'GUI closed'}; @{text=$text}|ConvertTo-Json -Compress"
                        text=ops.powershell(diagnostic)['text']
                        print('::error title=Isolated updater window::'+text.replace('%','%25').replace('\r','%0D').replace('\n','%0A'),flush=True)
                        packages=Path(os.environ['LOCALAPPDATA'])/'SaisBlueCRM/packages'
                        for manifest in sorted(packages.glob('*/release.json'),key=lambda p:p.stat().st_mtime)[-2:]:
                            record=json.loads(manifest.read_text())
                            print('::error title=Downloaded public release manifest::'+json.dumps({k:record.get(k) for k in ('version','commit','sha256')}),flush=True)
                    self.assertTrue(ops.health(release_version),'GUI update did not start the verified new version')
                    self.assertEqual((root/'.env').read_text(encoding='utf-8'),config)
                    with sqlite_connection(root/'data/crm.sqlite3') as db:
                        self.assertEqual(db.execute("SELECT name FROM contacts WHERE id='fixture'").fetchone()[0],'Preserved customer')
                    # Close the browser spawned by the GUI is unnecessary; stop this CRM via the same validated controller.
                    ops.stop()
                else:
                    while time.monotonic()<deadline and ops.health():time.sleep(.5)
                    if ops.health():
                        diagnostic=code.split('$deadline=')[0]+"\n$p=Get-Process -Id "+str(result['pid'])+"; $text=@([SaisBlueGui]::Children($p.MainWindowHandle)|ForEach-Object {[SaisBlueGui]::Text($_)}) -join '; '; @{text=$text}|ConvertTo-Json -Compress"
                        text=ops.powershell(diagnostic)['text']
                        print('::error title=Updater window state::'+text.replace('%','%25').replace('\n','%0A'),flush=True)
                        inventory=ops.snapshot()
                        safe=json.dumps({'root_aliases':ops.root_aliases,**inventory})
                        print('::error title=Isolated fixture processes::'+safe.replace('%','%25').replace('\n','%0A'),flush=True)
                        expected=ops.powershell("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); @(Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -eq "+str(crm.pid)+" -or $_.ParentProcessId -eq "+str(crm.pid)+"}|Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine)|ConvertTo-Json -Compress")
                        print('::error title=Expected fixture Python only::'+json.dumps(expected).replace('%','%25').replace('\n','%0A'),flush=True)
                        try:ops.stop()
                        except Exception as exc:
                            print('::error title=Direct controller diagnostic::'+str(exc).replace('%','%25').replace('\n','%0A'),flush=True)
                        self.fail('GUI did not stop the old CRM; see safe fixture diagnostics')
                self.assertIsNone(other.poll(),'Updater stopped an unrelated Python process')
                # WM_CLOSE waits until the update has finished; use exact GUI PID only.
                ops.powershell('$p=Get-Process -Id '+str(result['pid'])+' -ErrorAction SilentlyContinue; if($p){$p.CloseMainWindow()|Out-Null}')
            finally:
                from automatic_start import set_enabled, task_prelude
                set_enabled(root,False)
                try:ops.powershell(task_prelude(root)+"if($match){Stop-ScheduledTask -TaskName $name; Unregister-ScheduledTask -TaskName $name -Confirm:$false}")
                except Exception:pass
                try:ops.stop()
                except Exception:pass
                if crm.poll() is None:crm.terminate()
                crm.wait(timeout=10)
                other.terminate();other.wait(timeout=10)


    def test_boot_task_recovers_app_and_orphan_tunnel_without_interactive_login(self):
        from automatic_start import install, set_enabled, task_prelude
        from desktop_worker import WindowsOps, process_roles, update_lock
        class FixtureOps(WindowsOps):
            def powershell(self,code,timeout=35):
                encoded=base64.b64encode(code.encode('utf-16le')).decode('ascii')
                exe=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
                result=subprocess.run([str(exe),'-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode:
                    # Only this isolated fixture: no company credentials exist.
                    raise AssertionError(result.stderr.decode('utf-8',errors='replace')[:4000])
                value=result.stdout.decode('utf-8-sig').strip()
                return json.loads(value) if value else None
        source=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='SaisBlue boot test ') as folder:
            root=Path(folder).resolve()
            subprocess.run([sys.executable,'-m','venv','--without-pip','--system-site-packages',root/'.venv'],check=True,capture_output=True)
            for script in source.glob('*.py'):
                if not script.name.startswith('test_'):shutil.copyfile(script,root/script.name)
            # Exercise the production monitor in a real S4U batch session. Only
            # shorten the polling wait for this isolated CI fixture.
            monitor=root/'supervise_crm.py'
            monitor.write_text(monitor.read_text(encoding='utf-8').replace('sys.exit(run())','sys.exit(run(poll_interval=2))'),encoding='utf-8')
            (root/'server.py').write_text("RELEASE = 'fixture'\n",encoding='utf-8')
            (root/'data').mkdir()
            with sqlite_connection(root/'data/crm.sqlite3') as db:db.execute('CREATE TABLE preserved(name TEXT)')
            config='CRM_DB=data/crm.sqlite3\nCRM_LISTEN_HOST=127.0.0.1\n'
            (root/'.env').write_text(config,encoding='utf-8')
            app='''import json,os,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from runtime_control import Runtime
root=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'ok':True,'application':'sais-blue-crm','version':'fixture'}).encode())
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',3000),Handler)
runtime=Runtime(root,'app');stop=threading.Event()
runtime.watch(lambda:threading.Thread(target=server.shutdown,daemon=True).start(),stop)
runtime.update('ready')
try:server.serve_forever()
finally:stop.set();server.server_close();runtime.close()
'''
            (root/'launch.py').write_text(app,encoding='utf-8')
            (root/'tools').mkdir()
            agent=root/'tools/Agent.cs'
            agent.write_text('using System; using System.Threading; class Agent { static void Main(string[] args) { if(args.Length>0 && args[0]=="version") {Console.WriteLine("ngrok version fixture");return;} while(true) Thread.Sleep(1000); } }')
            compiler=Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
            subprocess.run([str(compiler),'/nologo','/out:'+str(root/'tools/ngrok.exe'),str(agent)],check=True,capture_output=True)
            controller='''import subprocess,sys,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
from runtime_control import Runtime
root=Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(404);self.end_headers()
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',3002),Handler)
runtime=Runtime(root,'https');stop=threading.Event()
runtime.watch(lambda:threading.Thread(target=server.shutdown,daemon=True).start(),stop)
child=subprocess.Popen([str(root/'tools/ngrok.exe'),'http','http://127.0.0.1:3002','--config='+str(root/'.runtime/ngrok.yml')])
runtime.update('ready',callback='https://fixture.ngrok-free.dev/webhooks/whatsapp')
try:server.serve_forever()
finally:child.terminate();child.wait(timeout=5);stop.set();server.server_close();runtime.close()
'''
            (root/'iniciar_https.py').write_text(controller,encoding='utf-8')
            ops=FixtureOps(root,{})
            def wait_for(predicate):
                deadline=time.monotonic()+65
                while time.monotonic()<deadline:
                    if predicate():return
                    time.sleep(1)
                marker=root/'.runtime/supervisor.json'
                self.fail('Native recovery not confirmed. Safe monitor state: '+(marker.read_text() if marker.exists() else 'no heartbeat'))
            def inventory():return process_roles(ops.snapshot(),str(root))
            def controllers():return {pid for pid,(_,role) in inventory().items() if role=='https'}
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(600)'])
            try:
                # Start the monitor using Windows Task Scheduler, not this test's
                # interactive process. No live Meta credentials or ngrok account.
                sid=ops.powershell("@{sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value}|ConvertTo-Json -Compress")['sid']
                install(ops,sid)
                details=ops.powershell(task_prelude(root)+"@{logon=[string]$task.Principal.LogonType;level=[string]$task.Principal.RunLevel;triggers=@($task.Triggers|ForEach-Object {$_.CimClass.CimClassName})}|ConvertTo-Json -Compress")
                self.assertEqual(details['logon'],'S4U')
                self.assertEqual(details['level'],'Limited')
                self.assertIn('MSFT_TaskBootTrigger',details['triggers'])
                wait_for(ops.health)
                (root/'.env').write_text(config+'NGROK_AUTHTOKEN=fixture-not-real\n',encoding='utf-8')
                wait_for(lambda:bool(controllers()))
                # Kill only the exact port-owning app and observe its recovery.
                snapshot=ops.snapshot()
                pid=next(p['pid'] for p in snapshot['ports'] if p['port']==3000)
                ops.kill(process_roles(snapshot,str(root))[pid][0])
                wait_for(ops.health)
                # Kill a gateway; leave its child alive to test orphan cleanup.
                original=controllers()
                snapshot=inventory()
                for pid in original:ops.kill(snapshot[pid][0])
                wait_for(lambda:bool(controllers()-original))
                self.assertEqual(sum(role=='ngrok' for _,role in inventory().values()),1)
                self.assertIsNone(unrelated.poll())
                with update_lock(root):
                    set_enabled(root,False)
                    ops.stop()
                time.sleep(6)
                self.assertFalse(ops.health(),'Intentional stop was ignored')
                set_enabled(root,True)
                wait_for(ops.health)
            finally:
                set_enabled(root,False)
                try:ops.powershell(task_prelude(root)+"if($match){Stop-ScheduledTask -TaskName $name; Unregister-ScheduledTask -TaskName $name -Confirm:$false}")
                except Exception:pass
                try:ops.stop()
                except Exception:pass
                unrelated.terminate();unrelated.wait(timeout=10)


if __name__=='__main__':unittest.main()
