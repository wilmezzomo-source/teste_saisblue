from sqlite_context import connection as sqlite_connection
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from desktop_worker import UpdateError, process_roles, update_installation, update_lock, validate_target


class DesktopUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.source=Path(self.temp.name)/'package'
        self.target=Path(self.temp.name)/'installed'
        for folder in (self.source/'public/data',self.source/'desktop',self.target/'data',self.target/'.venv/Scripts'):
            folder.mkdir(parents=True)
        for name in ('launch.py','qualification.py','runtime_control.py','desktop_worker.py'):
            (self.source/name).write_text('new code',encoding='utf-8')
        (self.source/'server.py').write_text("RELEASE = '2026.11.06.5'\n",encoding='utf-8')
        (self.source/'requirements.txt').write_text('same dependencies')
        (self.source/'public/index.html').write_text('new UI')
        (self.source/'public/data/cities.json').write_text('[]')
        (self.source/'desktop/SaisBlue-Atualizador.exe').write_bytes(b'MZ-fixture')
        (self.source/'.env').write_text('META_ACCESS_TOKEN=must-not-copy')
        (self.target/'server.py').write_text('previous code')
        (self.target/'requirements.txt').write_text('same dependencies')
        (self.target/'launch.py').write_text('previous launcher')
        (self.target/'public').mkdir()
        (self.target/'public/index.html').write_text('previous UI')
        (self.target/'INICIAR-NO-WINDOWS.cmd').write_text('previous command')
        (self.target/'.venv/Scripts/python.exe').write_bytes(b'installed-python')
        (self.target/'.env').write_text('CRM_DB=data/crm.sqlite3\nCRM_LISTEN_HOST=192.168.0.219\nMETA_ACCESS_TOKEN=private-fixture\nMETA_WEBHOOK_URL=https://same.ngrok-free.dev/webhooks/whatsapp\n')
        with sqlite_connection(self.target/'data/crm.sqlite3') as db:
            db.execute('CREATE TABLE contacts(name TEXT)')
            db.execute("INSERT INTO contacts VALUES('Cliente preservado')")
        self.socket=patch('update_windows.socket.socket').start()
        self.socket.return_value.__enter__.return_value.connect_ex.return_value=111
        self.messages=[]

    def tearDown(self):
        patch.stopall();self.temp.cleanup()

    def ops(self, fail=False):
        target=self.target
        class Ops:
            calls=[]
            validated=0
            def stop(self):self.calls.append('stop')
            def validate(self):
                self.calls.append('validate');self.validated+=1
                if fail and self.validated==1:
                    with sqlite_connection(target/'data/crm.sqlite3') as db:
                        db.execute('ALTER TABLE contacts ADD COLUMN partial_migration TEXT')
                    raise UpdateError('Fixture migration failure')
            def start(self,version=None):self.calls.append(('start',version));return True
        return Ops()

    def report(self,message,**fields):self.messages.append((message,fields))

    def test_one_update_preserves_state_and_restarts_verified_version(self):
        config=(self.target/'.env').read_bytes()
        ops=self.ops()
        result=update_installation(self.source,self.target,ops,self.report,install=False)
        self.assertEqual(result['version'],'2026.11.06.5')
        self.assertEqual(ops.calls,['stop','validate',('start','2026.11.06.5')])
        self.assertEqual((self.target/'.env').read_bytes(),config)
        self.assertEqual((self.target/'.venv/Scripts/python.exe').read_bytes(),b'installed-python')
        self.assertEqual((self.target/'desktop/SaisBlue-Atualizador.exe').read_bytes(),b'MZ-fixture')
        with sqlite_connection(self.target/'data/crm.sqlite3') as db:
            self.assertEqual(db.execute('SELECT name FROM contacts').fetchone()[0],'Cliente preservado')
        self.assertNotIn('private-fixture',str(self.messages))

    def test_failed_migration_restores_database_code_and_removes_new_files(self):
        ops=self.ops(fail=True)
        config=(self.target/'.env').read_bytes()
        with self.assertRaisesRegex(UpdateError,'recuperada e o CRM reiniciado'):
            update_installation(self.source,self.target,ops,self.report,install=False)
        self.assertEqual((self.target/'server.py').read_text(),'previous code')
        self.assertEqual((self.target/'public/index.html').read_text(),'previous UI')
        self.assertEqual((self.target/'.env').read_bytes(),config)
        self.assertFalse((self.target/'qualification.py').exists())
        self.assertEqual(ops.calls[-1],('start',None))
        with sqlite_connection(self.target/'data/crm.sqlite3') as db:
            self.assertEqual([r[1] for r in db.execute('PRAGMA table_info(contacts)')],['name'])
            self.assertEqual(db.execute('SELECT name FROM contacts').fetchone()[0],'Cliente preservado')

    def test_incomplete_package_does_not_stop_running_crm(self):
        (self.source/'runtime_control.py').unlink()
        ops=self.ops()
        with self.assertRaisesRegex(UpdateError,'incompleto'):
            update_installation(self.source,self.target,ops,self.report,install=False)
        self.assertEqual(ops.calls,[])

    def test_backup_failure_restarts_original_application(self):
        ops=self.ops()
        with patch('desktop_worker.apply_update',side_effect=OSError('disk full')):
            with self.assertRaises(UpdateError):
                update_installation(self.source,self.target,ops,self.report,install=False)
        self.assertEqual(ops.calls,['stop',('start',None)])

    def test_lock_rejects_competing_updaters_and_recovers_after_exit(self):
        with update_lock(self.target):
            with self.assertRaises(UpdateError):
                with update_lock(self.target):pass
        with update_lock(self.target):pass

    def test_validation_requires_real_existing_database(self):
        root,config=validate_target(self.target)
        self.assertEqual(root,self.target.resolve())
        (self.target/'data/crm.sqlite3').unlink()
        with self.assertRaises(UpdateError):validate_target(self.target)


class ProcessScopeTest(unittest.TestCase):
    root=r'C:\SaisBlueCRM'
    def process(self,pid,script,exe=None,parent=0):
        return {'pid':pid,'parent':parent,'exe':exe or self.root+r'\.venv\Scripts\python.exe','command':'python.exe "'+self.root+'\\'+script+'" serve','started':'fixture-time'}

    def test_stops_only_own_app_wrapper_gateway_and_its_ngrok(self):
        rows=[self.process(10,'launch.py',parent=12),self.process(11,'iniciar_https.py'),self.process(12,'setup_windows.py'),
              self.process(90,'desktop_worker.py'),self.process(91,'diagnostico_whatsapp.py')]
        rows += [{'pid':13,'parent':11,'exe':r'C:\WindowsApps\ngrok.exe','command':'ngrok http http://127.0.0.1:3002 --inspect=false'},
                 {'pid':14,'parent':999,'exe':r'C:\WindowsApps\ngrok.exe','command':'ngrok http http://127.0.0.1:8000'},
                 {'pid':15,'parent':0,'exe':r'C:\Other\.venv\Scripts\python.exe','command':r'python C:\Other\launch.py serve'}]
        result=process_roles({'processes':rows,'ports':[{'port':3000,'pid':10},{'port':3002,'pid':11}]},self.root)
        self.assertEqual(set(result),{10,11,12,13})

    def test_same_port_unknown_process_or_similar_folder_is_never_killed(self):
        row=self.process(10,'launch.py')
        row['command']=row['command'].replace('SaisBlueCRM','SaisBlueCRM-other')
        for snapshot in ({'processes':[],'ports':[{'port':3000,'pid':999}]}, {'processes':[row],'ports':[{'port':3000,'pid':10}]}):
            with self.assertRaises(UpdateError):process_roles(snapshot,self.root)

    def test_pid_without_absolute_project_script_does_not_establish_identity(self):
        p=self.process(10,'launch.py');p['command']='python launch.py serve'
        with self.assertRaises(UpdateError):process_roles({'processes':[p],'ports':[{'port':3000,'pid':10}]},self.root)

    def test_store_ngrok_without_executable_path_still_requires_owned_parent_and_gateway(self):
        controller=self.process(11,'iniciar_https.py')
        child={'pid':12,'parent':11,'name':'ngrok.exe','exe':None,'command':'ngrok http http://127.0.0.1:3002 --inspect=false'}
        other={**child,'pid':99,'parent':555}
        roles=process_roles({'processes':[controller,child,other],'ports':[]},self.root)
        self.assertEqual(set(roles),{11,12})


if __name__=='__main__':unittest.main()
