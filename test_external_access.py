"""The configured external port is an exact browser origin, not a bind-port change."""
import unittest

import test_access_control as fixtures

EXTERNAL='http://200.225.129.156:3001'
LAN='http://192.168.0.219:3000'


class ExternalAccessTest(unittest.TestCase):
    setUp=fixtures.AccessControlTest.setUp
    tearDown=fixtures.AccessControlTest.tearDown
    login=fixtures.AccessControlTest.login

    def prepare(self):
        self.app.config.update(APP_URL=LAN,ACCESS_URL=EXTERNAL)
        client=self.app.test_client()
        login=client.post('/api/login',base_url=EXTERNAL,headers={'Origin':EXTERNAL},
                          json={'email':'grasi@example.test','password':'fixture-password-123'})
        self.assertEqual(login.status_code,200,login.json)
        return client,login.json['csrf']

    def test_external_login_writes_and_team_links_use_port_3001_and_preserve_lan(self):
        client,csrf=self.prepare()
        status=client.get('/api/status',base_url=EXTERNAL).json
        self.assertEqual(status['team_url'],EXTERNAL);self.assertEqual(status['access_url'],EXTERNAL)
        result=client.post('/api/contacts',base_url=EXTERNAL,headers={'Origin':EXTERNAL,'X-CSRF-Token':csrf},
                           json={'name':'Contato externo','phone':'5554999999777','city_id':'4309407'})
        self.assertEqual(result.status_code,201,result.json)
        lan=self.app.test_client().post('/api/login',base_url=LAN,headers={'Origin':LAN},
                            json={'email':'grasi@example.test','password':'fixture-password-123'})
        self.assertEqual(lan.status_code,200)
        self.assertEqual(self.app.config['APP_URL'],LAN)

    def test_other_ports_hosts_and_cross_origin_requests_stay_blocked_and_csrf_is_required(self):
        self.prepare()
        for host,origin in ((EXTERNAL,'http://200.225.129.156:3000'),(EXTERNAL,'https://evil.test'),(LAN,EXTERNAL)):
            result=self.app.test_client().post('/api/login',base_url=host,headers={'Origin':origin},
                                json={'email':'grasi@example.test','password':'fixture-password-123'})
            self.assertEqual(result.status_code,403,(host,origin,result.json))
        client,csrf=self.prepare()
        self.assertEqual(client.post('/api/followups',base_url=EXTERNAL,headers={'Origin':EXTERNAL},json={}).status_code,403)
        self.assertEqual(self.app.test_client().get('/api/contacts',base_url=EXTERNAL).status_code,401)

    def test_http_access_does_not_claim_iphone_push_or_change_meta_credentials(self):
        before={k:self.app.config.get(k) for k in ('META_APP_SECRET','META_PHONE_NUMBER_ID','META_ACCESS_TOKEN','PUBLIC_URL')}
        client,csrf=self.prepare()
        result=client.get('/api/push/config',base_url=EXTERNAL)
        self.assertEqual(result.status_code,200,result.json);self.assertFalse(result.json['secure'])
        self.assertEqual(before,{k:self.app.config.get(k) for k in before})


if __name__=='__main__':unittest.main()
