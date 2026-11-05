import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from configure_connections import EXPECTED_PHONE, lan_values, private_ip, read_config, save_config, verify_meta


class ConnectionTest(unittest.TestCase):
    def test_lan_config_preserves_data_and_credentials(self):
        existing={'CRM_DB':'data/existing.sqlite3','META_ACCESS_TOKEN':'private-test-value','APP_ENV':'development','APP_URL':'http://127.0.0.1:3000','ALLOW_SIMULATION':'1'}
        changed=lan_values(existing,'192.168.10.25')
        self.assertEqual(changed['CRM_DB'],existing['CRM_DB'])
        self.assertEqual(changed['META_ACCESS_TOKEN'],existing['META_ACCESS_TOKEN'])
        self.assertEqual(changed['CRM_LISTEN_HOST'],'192.168.10.25')
        self.assertEqual(changed['APP_URL'],'http://192.168.10.25:3000')
        self.assertEqual(changed['ALLOW_SIMULATION'],'0')
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'.env'
            save_config(changed,config)
            self.assertEqual(read_config(config),changed)

    def test_no_public_binding_and_no_https_downgrade(self):
        for invalid in ['0.0.0.0','127.0.0.1','8.8.8.8','169.254.1.1','192.0.2.1','::1']:
            with self.assertRaises(ValueError):
                private_ip(invalid)
        for valid in ['192.168.1.10','10.0.0.10','172.16.0.10']:
            self.assertEqual(private_ip(valid),valid)
        with self.assertRaises(ValueError):
            lan_values({'APP_ENV':'production'},'192.168.1.10')

    def test_meta_validates_exact_business_number_without_token_in_url(self):
        def sender(req,timeout):
            self.assertNotIn('fake-private-token',req.full_url)
            self.assertEqual(req.headers['Authorization'],'Bearer fake-private-token')
            return io.BytesIO(json.dumps({'display_phone_number':'+55 54 3443-6405','verified_name':'Sais Blue'}).encode())
        result=verify_meta('123456','fake-private-token','v22.0',sender)
        self.assertEqual(result['verified_name'],'Sais Blue')
        def wrong_sender(req,timeout):
            return io.BytesIO(b'{"display_phone_number":"+55 11 99999-1111"}')
        with self.assertRaisesRegex(ValueError,'não é'):
            verify_meta('123456','fake-private-token','v22.0',wrong_sender)
        def refused(req,timeout):
            raise urllib.error.HTTPError(req.full_url,401,'denied',{},None)
        with self.assertRaises(ValueError) as error:
            verify_meta('123456','fake-private-token','v22.0',refused)
        self.assertNotIn('fake-private-token',str(error.exception))

if __name__=='__main__':
    unittest.main()
