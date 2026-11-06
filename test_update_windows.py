import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from update_windows import apply_update


class UpdateTest(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.source=Path(self.temp.name)/'new'
        self.target=Path(self.temp.name)/'installed'
        for directory in ['new/public/data','new/public/brand','new/data','installed/data','installed/.venv']:
            (Path(self.temp.name)/directory).mkdir(parents=True)
        for name in ['server.py','launch.py','qualification.py','requirements.txt']:
            (self.source/name).write_text('new code')
        (self.source/'public/index.html').write_text('new interface')
        (self.source/'public/data/cities.json').write_text('[]')
        (self.source/'public/brand/sb-logo.png').write_bytes(b'test-logo')
        (self.source/'.env').write_text('CRM_DB=wrong.sqlite3\nMETA_ACCESS_TOKEN=must-not-copy')
        (self.source/'data/crm.sqlite3').write_bytes(b'never copy this')
        (self.target/'server.py').write_text('old code')
        (self.target/'INICIAR-NO-WINDOWS.cmd').write_text('existing launcher')
        (self.target/'.env').write_text('CRM_DB=data/crm.sqlite3\nMETA_ACCESS_TOKEN=keep-existing\nCRM_LISTEN_HOST=192.168.1.25\n')
        (self.target/'.venv/keep.txt').write_text('existing environment')
        with sqlite3.connect(self.target/'data/crm.sqlite3') as db:
            db.execute('CREATE TABLE contacts(name TEXT)')
            db.execute("INSERT INTO contacts VALUES('Cliente existente')")
        self.socket=patch('update_windows.socket.socket').start()
        self.socket.return_value.__enter__.return_value.connect_ex.return_value=111

    def tearDown(self):
        patch.stopall()
        self.temp.cleanup()

    def test_update_keeps_contacts_configuration_and_environment(self):
        config=(self.target/'.env').read_bytes()
        backup=apply_update(self.source,self.target,install=False)
        self.assertEqual((self.target/'.env').read_bytes(),config)
        self.assertEqual((self.target/'.venv/keep.txt').read_text(),'existing environment')
        self.assertEqual((self.target/'server.py').read_text(),'new code')
        self.assertEqual((self.target/'qualification.py').read_text(),'new code')
        self.assertEqual((self.target/'public/brand/sb-logo.png').read_bytes(),b'test-logo')
        for path in [self.target/'data/crm.sqlite3',backup/'crm.sqlite3']:
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT name FROM contacts').fetchone()[0],'Cliente existente')
        import zipfile
        with zipfile.ZipFile(backup/'codigo-anterior.zip') as previous:
            self.assertEqual(previous.read('server.py'),b'old code')
            self.assertNotIn('.env',previous.namelist())

    def test_running_app_aborts_before_replacing_files(self):
        self.socket.return_value.__enter__.return_value.connect_ex.return_value=0
        with self.assertRaisesRegex(ValueError,'ainda está rodando'):
            apply_update(self.source,self.target,install=False)
        self.assertEqual((self.target/'server.py').read_text(),'old code')
        self.assertFalse((self.target/'backups').exists())
