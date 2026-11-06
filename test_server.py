import hashlib
import hmac
import io
import json
import secrets
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server import create_app, database, password


class CRMTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': self.temp.name + '/test.db',
                               'META_APP_SECRET': 'test-secret', 'META_VERIFY_TOKEN': 'verify-test',
                               'META_PHONE_NUMBER_ID': '123456', 'META_ACCESS_TOKEN': '',
                               'ALLOW_SIMULATION': True, 'APP_URL': '', 'SECURE_COOKIE': False})
        self.client = self.app.test_client()
        self.member = self.app.test_client()
        with database(self.app) as db:
            hashed = password('test-password-123')
            for uid, role in [('admin-id','admin'), ('member-id','member')]:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)', (uid, role+'@example.test', role, hashed, role, time.time()))
        self.admin_csrf = self.login(self.client, 'admin')
        self.member_csrf = self.login(self.member, 'member')

    def tearDown(self):
        self.temp.cleanup()

    def login(self, client, role):
        response = client.post('/api/login', json={'email':role+'@example.test','password':'test-password-123'})
        self.assertEqual(response.status_code, 200)
        return response.json['csrf']

    def post(self, path, data, client=None, csrf=None):
        return (client or self.client).post(path, json=data, headers={'X-CSRF-Token':csrf or self.admin_csrf})

    def simulate(self):
        r = self.post('/api/simulate', {'name':'Lead teste', 'phone':'5511999991234', 'body':'Vim do anúncio','city_id':'4302105'})
        self.assertEqual(r.status_code, 200)
        return self.client.get('/api/contacts').json['contacts'][0]

    def signed(self, payload):
        raw = json.dumps(payload).encode()
        signature = 'sha256=' + hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()
        return self.client.post('/webhooks/whatsapp', data=raw, content_type='application/json', headers={'X-Hub-Signature-256':signature})

    def meta_payload(self, timestamp=None, number_id='123456'):
        return {'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':number_id},'contacts':[{'wa_id':'5521999991111','profile':{'name':'Lead Meta'}}], 'messages':[{'id':'wamid.test.1','from':'5521999991111','timestamp':str(timestamp or int(time.time())),'type':'text','text':{'body':'Olá pelo anúncio'},'referral':{'source_type':'ad','source_id':'ad123','headline':'Campanha Sais Blue'}}]}}]}]}

    def test_login_csrf_logout_and_protected_data(self):
        anonymous = self.app.test_client()
        for path in ['/api/contacts','/api/team','/api/status','/api/me']:
            self.assertEqual(anonymous.get(path).status_code, 401)
        self.assertEqual(anonymous.post('/api/messages',json={'body':'test'}).status_code,401)
        self.assertEqual(self.client.post('/api/contacts',json={'name':'A','phone':'5511999991111','city_id':'4302105'}).status_code,403)
        r = self.post('/api/contacts', {'name':'A','phone':'5511999991111','city_id':'4302105'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.post('/api/logout', {}).status_code,200)
        self.assertEqual(self.client.get('/api/contacts').status_code,401)

    def test_secure_session_cookie_and_origin(self):
        self.app.config['SECURE_COOKIE'] = True
        r = self.client.post('/api/login',json={'email':'admin@example.test','password':'test-password-123'})
        cookie = r.headers['Set-Cookie']
        self.assertIn('HttpOnly',cookie)
        self.assertIn('Secure',cookie)
        self.assertIn('SameSite=Lax',cookie)
        r = self.member.post('/api/contacts',json={'name':'A','phone':'5511999991111','city_id':'4302105'},headers={'X-CSRF-Token':self.member_csrf,'Origin':'https://evil.test'})
        self.assertEqual(r.status_code,403)

    def test_capture_dedup_and_shared_member_edit(self):
        c = self.simulate()
        self.simulate()
        rows = self.member.get('/api/contacts').json['contacts']
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['messages']),2)
        r=self.post('/api/update', {'id':c['id'],'revision':rows[0]['revision'],'stage':'Em atendimento','value':1500},self.member,self.member_csrf)
        self.assertEqual(r.status_code,200)
        c=self.client.get('/api/contacts').json['contacts'][0]
        self.assertEqual(c['stage'],'Em atendimento')
        self.assertEqual(c['audit'][0]['actor'],'member')
        self.assertEqual(self.post('/api/messages',{'id':c['id'],'body':'Retornar amanhã'},self.member,self.member_csrf).status_code,200)
        self.assertEqual(self.client.get('/api/contacts').json['contacts'][0]['messages'][-1]['author'],'member')

    def test_stale_revision_cannot_overwrite(self):
        c=self.simulate()
        def edit(owner):
            client=self.app.test_client()
            csrf=self.login(client,'member')
            return self.post('/api/update',{'id':c['id'],'revision':c['revision'],'owner':owner},client,csrf).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(edit,['Pessoa A','Pessoa B']))
        self.assertEqual(sorted(results),[200,409])
        row=self.client.get('/api/contacts').json['contacts'][0]
        self.assertEqual(row['revision'],c['revision']+1)

    def test_invitation_is_one_time_and_member_cannot_manage_team(self):
        self.assertEqual(self.post('/api/invites',{'email':'new@example.test'},self.member,self.member_csrf).status_code,403)
        r=self.post('/api/invites',{'email':'new@example.test','role':'member'})
        token=r.json['path'].split('invite=')[1]
        new=self.app.test_client()
        fields={'token':token,'name':'Nova pessoa','password':'new-password-123'}
        accepted=new.post('/api/accept-invite',json=fields)
        self.assertEqual(accepted.status_code,200)
        self.assertEqual(accepted.json['user']['email'],'new@example.test')
        self.assertEqual(accepted.json['user']['role'],'member')
        self.assertEqual(new.post('/api/accept-invite',json=fields).status_code,403)
        self.assertEqual(new.get('/api/contacts').status_code,200)

    def test_disable_and_reset_revoke_existing_sessions(self):
        r=self.post('/api/team/reset',{'id':'member-id'})
        reset=self.app.test_client()
        token=r.json['path'].split('invite=')[1]
        r=reset.post('/api/accept-invite',json={'token':token,'name':'member','password':'changed-password-123'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.member.get('/api/me').status_code,401)
        self.assertEqual(self.post('/api/team/update',{'id':'member-id','active':False}).status_code,200)
        self.assertEqual(reset.get('/api/me').status_code,401)
        self.assertEqual(self.post('/api/team/update',{'id':'admin-id','active':False}).status_code,400)

    def test_login_throttle(self):
        client=self.app.test_client()
        for i in range(10):
            self.assertEqual(client.post('/api/login',json={'email':'missing@example.test','password':'wrong'}).status_code,401)
        self.assertEqual(client.post('/api/login',json={'email':'missing@example.test','password':'wrong'}).status_code,429)

    def test_signed_webhook_replay_window_and_account(self):
        payload=self.meta_payload(timestamp=int(time.time()-300))
        self.assertEqual(self.signed(payload).status_code,200)
        self.assertEqual(self.signed(payload).status_code,200)
        rows=self.client.get('/api/contacts').json['contacts']
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['messages']),1)
        self.assertLess(rows[0]['messages'][0]['created'],time.time()-250)
        self.assertEqual(json.loads(rows[0]['referral'])['source_id'],'ad123')
        self.assertEqual(self.signed(self.meta_payload(number_id='other-number')).status_code,200)
        self.assertEqual(self.client.post('/webhooks/whatsapp',json=payload).status_code,403)
        r=self.client.get('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-test&hub.challenge=challenge123')
        self.assertEqual(r.data,b'challenge123')

    def test_send_guard_missing_credentials_and_simulation_window(self):
        c=self.simulate()
        fields={'id':c['id'],'body':'Olá','request_id':secrets.token_hex(16)}
        self.assertEqual(self.post('/api/send',fields).status_code,503)
        self.app.config['META_ACCESS_TOKEN']='fake-token'
        self.assertEqual(self.post('/api/send',fields).status_code,409)

    def test_send_adapter_idempotence_and_delivery_status(self):
        self.signed(self.meta_payload())
        c=self.client.get('/api/contacts').json['contacts'][0]
        sent=[]
        def fake_sender(req,timeout):
            sent.append(json.loads(req.data))
            self.assertEqual(req.headers['Authorization'],'Bearer fake-token')
            return io.BytesIO(b'{"messages":[{"id":"wamid.out.1"}]}')
        self.app.config.update(META_ACCESS_TOKEN='fake-token',META_SENDER=fake_sender)
        fields={'id':c['id'],'body':'Podemos ajudar!','request_id':secrets.token_hex(16)}
        self.assertEqual(self.post('/api/send',fields).json['status'],'accepted')
        self.assertEqual(self.post('/api/send',fields).json['duplicate'],True)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0]['to'],c['phone'])
        payload={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'123456'},'statuses':[{'id':'wamid.out.1','status':'read'}]}}]}]}
        self.signed(payload)
        payload['entry'][0]['changes'][0]['value']['statuses'][0]['status']='sent'
        self.signed(payload)
        messages=self.client.get('/api/contacts').json['contacts'][0]['messages']
        self.assertEqual(next(m for m in messages if m['direction']=='out')['status'],'read')

    def test_failed_delivery_keeps_meta_error_code_in_history(self):
        self.signed(self.meta_payload())
        c=self.client.get('/api/contacts').json['contacts'][0]
        self.app.config.update(META_ACCESS_TOKEN='fake-token',META_SENDER=lambda req,timeout:io.BytesIO(b'{"messages":[{"id":"wamid.fail.1"}]}'))
        self.post('/api/send',{'id':c['id'],'body':'Teste','request_id':secrets.token_hex(16)})
        event={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'123456'},'statuses':[{'id':'wamid.fail.1','status':'failed','errors':[{'code':131000,'message':'private raw body should not be stored'}]}]}}]}]}
        self.signed(event)
        message=next(m for m in self.client.get('/api/contacts').json['contacts'][0]['messages'] if m['direction']=='out')
        self.assertEqual(message['status'],'failed')
        self.assertEqual(message['error_code'],131000)
        self.assertNotIn('private raw',message['error_detail'])

    def test_timeout_not_automatically_retried(self):
        self.signed(self.meta_payload())
        c=self.client.get('/api/contacts').json['contacts'][0]
        calls=[]
        def fake_sender(req,timeout):
            calls.append(1)
            raise TimeoutError()
        self.app.config.update(META_ACCESS_TOKEN='fake-token',META_SENDER=fake_sender)
        fields={'id':c['id'],'body':'Olá','request_id':secrets.token_hex(16)}
        self.assertEqual(self.post('/api/send',fields).status_code,502)
        self.assertEqual(self.post('/api/send',fields).json['status'],'uncertain')
        self.assertEqual(len(calls),1)

    def test_admin_cli_and_consistent_backup(self):
        from unittest.mock import patch
        runner = self.app.test_cli_runner()
        with patch('server.getpass.getpass', return_value='another-password-123'):
            result = runner.invoke(args=['create-admin','--email','owner@example.test','--name','Owner'])
        self.assertEqual(result.exit_code,0,result.output)
        self.assertNotIn('another-password-123',result.output)
        self.simulate()
        backup=Path(self.temp.name)/'backup.db'
        result=runner.invoke(args=['backup',str(backup)])
        self.assertEqual(result.exit_code,0,result.output)
        with sqlite3.connect(backup) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],3)

    def test_required_location_and_instagram_normalization(self):
        self.signed(self.meta_payload())
        row=self.client.get('/api/contacts').json['contacts'][0]
        fields={'id':row['id'],'revision':row['revision']}
        self.assertEqual(self.post('/api/update',{**fields,'city_id':'invalid'}).status_code,400)
        response=self.post('/api/update',{**fields,'city_id':'4302105','city':'Cidade inventada','state':'XX','instagram':'https://www.instagram.com/SaisBlue/?utm_source=test'})
        self.assertEqual(response.status_code,200)
        row=self.client.get('/api/contacts').json['contacts'][0]
        self.assertEqual((row['city'],row['state'],row['instagram']),('Bento Gonçalves','RS','saisblue'))
        self.assertFalse(row['location_pending'])
        self.assertAlmostEqual(row['latitude'],-29.1662,places=3)
        fields={'id':row['id'],'revision':row['revision']}
        self.assertEqual(self.post('/api/update',{**fields,'city_id':''}).status_code,400)
        self.assertEqual(self.post('/api/update',{**fields,'instagram':'https://evil.test/saisblue'}).status_code,400)
        self.assertEqual(self.post('/api/update',{**fields,'instagram':'javascript:alert(1)'}).status_code,400)
        self.assertEqual(self.post('/api/update',{**fields,'city_id':'3550308','instagram':'@outro.perfil'}).status_code,200)
        row=self.client.get('/api/contacts').json['contacts'][0]
        self.assertEqual((row['city'],row['state'],row['instagram']),('São Paulo','SP','outro.perfil'))
        self.assertEqual(row['audit'][0]['actor'],'admin')

    def test_whatsapp_without_location_is_preserved_and_must_be_completed(self):
        self.assertEqual(self.signed(self.meta_payload()).status_code,200)
        row=self.client.get('/api/contacts').json['contacts'][0]
        self.assertTrue(row['location_pending'])
        self.assertIsNone(row['latitude'])
        self.assertEqual(len(row['messages']),1)
        self.assertEqual(self.post('/api/update',{'id':row['id'],'revision':row['revision'],'stage':'Em atendimento'}).status_code,400)
        self.assertEqual(self.post('/api/update',{'id':row['id'],'revision':row['revision'],'city_id':'4302105','stage':'Em atendimento'}).status_code,200)
        self.signed(self.meta_payload())
        row=self.client.get('/api/contacts').json['contacts'][0]
        self.assertFalse(row['location_pending'])
        self.assertEqual(len(row['messages']),1)
        self.assertEqual(row['city'],'Bento Gonçalves')

    def test_existing_prototype_migrates_without_data_loss(self):
        legacy=Path(self.temp.name)/'legacy.db'
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE contacts(id TEXT PRIMARY KEY,name TEXT,phone TEXT,stage TEXT,value REAL,owner TEXT,source TEXT,referral TEXT,note TEXT,created REAL,updated REAL)")
            db.execute("CREATE TABLE messages(id TEXT PRIMARY KEY,contact_id TEXT,body TEXT,direction TEXT,created REAL)")
            db.execute("INSERT INTO contacts VALUES('old','Contato existente','5511999991234','Ganho',120,'Equipe','Manual',NULL,'nota',1,1)")
        migrated=create_app({'TESTING':True,'DATABASE':str(legacy)})
        with database(migrated) as db:
            row=db.execute('SELECT * FROM contacts').fetchone()
            self.assertEqual(row['name'],'Contato existente')
            self.assertEqual(row['revision'],0)
            self.assertEqual(row['note'],'nota')

if __name__=='__main__':
    unittest.main()
