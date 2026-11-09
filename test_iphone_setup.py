"""The public gateway is prepared without replacing customer configuration or Meta."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import configurar_iphone as setup
from configure_connections import read_config


class IphoneSetupTest(unittest.TestCase):
    def test_prepare_is_idempotent_preserves_credentials_and_key_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'.env').write_text('APP_ENV=lan\nAPP_URL=http://192.168.0.219:3000\nCRM_LISTEN_HOST=192.168.0.219\nCRM_DB=data/customer.sqlite3\nMETA_ACCESS_TOKEN=private-fixture\nMETA_WEBHOOK_URL=https://old.ngrok-free.dev/webhooks/whatsapp\n',encoding='utf-8')
            with patch.object(setup.os,'startfile',create=True):
                request=setup.prepare(root,detect_ip=False)
                key=(root/'data'/'webpush-private.pem').read_bytes()
                setup.prepare(root,detect_ip=False)
            self.assertEqual(key,(root/'data'/'webpush-private.pem').read_bytes())
            values=read_config(root/'.env')
            self.assertEqual(values['META_ACCESS_TOKEN'],'private-fixture')
            self.assertEqual(values['APP_URL'],'http://192.168.0.219:3000')
            self.assertIn('old.ngrok',values['META_WEBHOOK_URL'])
            self.assertNotIn('private-fixture',request.read_text(encoding='utf-8-sig'))
            self.assertIn('CGNAT',request.read_text(encoding='utf-8-sig'))
            self.assertFalse((root/'tools'/'caddy.exe').exists())
            config=(root/'data'/'external'/'Caddyfile').read_text()
            self.assertIn('reverse_proxy 192.168.0.219:3000',config)
            self.assertIn('admin 127.0.0.1:2019',config)
            self.assertNotIn('private-fixture',config)

    def test_install_checks_digest_before_extracting_and_only_extracts_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as package:
                package.writestr('caddy.exe',b'fixture-binary')
                package.writestr('../../evil.txt',b'untrusted')
            raw=archive.getvalue()
            with self.assertRaises(ValueError):setup.install_caddy(Path(temp),opener=lambda *a,**kw:io.BytesIO(raw))
            self.assertFalse((Path(temp)/'tools').exists())
            with patch.object(setup,'CADDY_SHA512',hashlib.sha512(raw).hexdigest()):
                target=setup.install_caddy(Path(temp),opener=lambda *a,**kw:io.BytesIO(raw))
            self.assertEqual(target.read_bytes(),b'fixture-binary')
            self.assertEqual([p.name for p in Path(temp).rglob('*') if p.is_file()],['caddy.exe'])

    def test_windows_task_is_scoped_and_no_unrelated_service_is_stopped(self):
        root=Path('/tmp/CRM com espaço')
        script=setup.task_script(root,root/'tools'/'caddy.exe',root/'data'/'external'/'Caddyfile')
        self.assertIn('SaisBlueCRM-HTTPS-',script)
        self.assertIn('-LocalPort 80,443 -Program $exe',script)
        self.assertIn('throw',script)
        for banned in ['Stop-Process','Stop-Service','-LocalPort 3000','Set-NetFirewallProfile']:
            self.assertNotIn(banned,script)
        self.assertIn('New-ScheduledTaskTrigger -AtStartup',script)


if __name__=='__main__':unittest.main()
