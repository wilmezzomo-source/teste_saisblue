from sqlite_context import connection as sqlite_connection
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
import urllib.error
from validar_instalacao import check


class InstallationCheckTest(unittest.TestCase):
    def test_read_only_report_protects_secrets_and_checks_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['public/index.html','public/brand/sb-logo.png','public/data/cities.json','public/vendor/leaflet/leaflet.js']:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
            config='APP_URL=http://192.168.0.219:3000\nCRM_DB=crm.sqlite3\nMETA_ACCESS_TOKEN=private-test-token\n'
            (root/'.env').write_text(config)
            with sqlite_connection(root/'crm.sqlite3') as db:
                db.execute('CREATE TABLE users(active INTEGER)');db.execute('INSERT INTO users VALUES(1)')
                db.execute('CREATE TABLE contacts(id TEXT)');db.execute("INSERT INTO contacts VALUES('existing')")
            def sender(url,timeout):
                if url.endswith('/healthz'):return io.BytesIO(b'{"ok":true,"version":"2026.11.06.1"}')
                raise urllib.error.HTTPError(url,401,'login required',{},None)
            report='\n'.join(check(root,sender))
            self.assertIn('VERSAO: 2026.11.06.1',report)
            self.assertIn('LOGIN: OK',report)
            self.assertIn('1 usuário(s) ativo(s), 1 contato(s)',report)
            self.assertNotIn('private-test-token',report)
            self.assertEqual((root/'.env').read_text(),config)
