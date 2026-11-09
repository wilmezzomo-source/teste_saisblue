"""Exercise real durable dispatch and encryption, with no live provider requests."""
import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
import requests

from server import create_app, database, password
from web_push import public_key, validate_subscription, process_push_once
from notifications import notify_created

BASE='https://crm.saisblue.com.br'


def subscription(suffix='fixture'):
    key=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    encode=lambda v:base64.urlsafe_b64encode(v).decode().rstrip('=')
    return {'endpoint':'https://web.push.apple.com/'+suffix,'keys':{'p256dh':encode(key),'auth':encode(b'a'*16)}}


class WebPushTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.hashed=password('fixture-password-123')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'DATABASE':self.temp.name+'/crm.db','APP_URL':'http://192.168.0.219:3000','SECURE_COOKIE':False})
        self.sent=[]
        self.app.config['PUSH_SENDER']=lambda **kw:self.sent.append(kw)
        with database(self.app) as db:
            for n,(uid,role) in enumerate([('admin','admin'),('grasi','member'),('chai','member')]):
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',(uid,uid+'@example.test',uid,self.hashed,role,time.time()+n))
        self.clients={}
        for uid in ['admin','grasi','chai']:
            client=self.app.test_client()
            r=client.post('/api/login',base_url=BASE,json={'email':uid+'@example.test','password':'fixture-password-123'},headers={'Origin':BASE})
            self.assertEqual(r.status_code,200,r.json)
            self.clients[uid]=(client,r.json['csrf'])
        self.assertEqual(self.post('admin','/api/push/prepare',{}).status_code,200)
        self.sub=subscription()

    def tearDown(self): self.temp.cleanup()
    def post(self,uid,path,value,base=BASE):
        c,csrf=self.clients[uid]
        return c.post(path,base_url=base,json=value,headers={'X-CSRF-Token':csrf,'Origin':base})
    def get(self,uid,path): return self.clients[uid][0].get(path,base_url=BASE)
    def register(self,uid='grasi',sub=None):
        r=self.post(uid,'/api/push/subscribe',{'subscription':sub or self.sub})
        self.assertEqual(r.status_code,200,r.json)
    def lead(self):
        r=self.post('admin','/api/contacts',{'name':'Nome privado','phone':'5554999991234','city_id':'4309407','owner_id':'grasi'})
        self.assertEqual(r.status_code,201,r.json)
        return r.json['id']
    def jobs(self):
        with database(self.app) as db:return [dict(r) for r in db.execute('SELECT * FROM push_deliveries ORDER BY id')]
    def dispatch(self): return process_push_once(self.app,database)

    def test_public_assets_no_secrets_and_hybrid_https(self):
        anonymous=self.app.test_client()
        for route in ['/manifest.webmanifest','/service-worker.js','/offline.html','/brand/app-icon.png']:
            r=anonymous.get(route,base_url=BASE)
            self.assertEqual(r.status_code,200,route)
            r.close()
        for route in ['/api/push/config','/api/notifications/1']:
            self.assertEqual(anonymous.get(route,base_url=BASE).status_code,401)
        for route in ['/webpush-private.pem','/data/webpush-private.pem','/.env']:
            self.assertEqual(anonymous.get(route,base_url=BASE).status_code,404)
        response=self.get('grasi','/api/push/config')
        self.assertTrue(response.json['secure'])
        self.assertIn('max-age',response.headers['Strict-Transport-Security'])
        first=public_key(self.app)
        self.assertEqual(public_key(self.app,create=True),first)
        self.assertNotIn('PRIVATE',json.dumps(response.json))
        self.assertEqual(self.post('grasi','/api/push/prepare',{}).status_code,403)
        r=anonymous.get('/?notice=3',base_url='http://crm.saisblue.com.br')
        self.assertEqual(r.status_code,308)
        self.assertEqual(r.location,BASE+'/?notice=3')
        r=anonymous.post('/api/login',base_url=BASE,json={'email':'grasi@example.test','password':'fixture-password-123'},headers={'Origin':BASE})
        self.assertIn('Secure',r.headers['Set-Cookie'])
        local=self.app.test_client().post('/api/login',base_url='http://192.168.0.219:3000',json={'email':'grasi@example.test','password':'fixture-password-123'},headers={'Origin':'http://192.168.0.219:3000'})
        self.assertEqual(local.status_code,200)
        self.assertNotIn('Secure',local.headers['Set-Cookie'])
        self.assertEqual(anonymous.post('/api/login',base_url=BASE,json={},headers={'Origin':'https://evil.test'}).status_code,403)

    def test_provider_and_key_validation_prevent_arbitrary_requests(self):
        for endpoint in ['http://web.push.apple.com/a','https://localhost/a','https://web.push.apple.com.evil.test/a','https://user@web.push.apple.com/a','https://web.push.apple.com:444/a','https://web.push.apple.com/a#x']:
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):validate_subscription({**self.sub,'endpoint':endpoint})
        for keys in [{'p256dh':'x','auth':'x'}, {'p256dh':self.sub['keys']['p256dh'],'auth':'xx'}]:
            self.assertEqual(self.post('grasi','/api/push/subscribe',{'subscription':{**self.sub,'keys':keys}}).status_code,400)
        local=self.app.test_client()
        r=local.post('/api/login',base_url='http://192.168.0.219:3000',json={'email':'grasi@example.test','password':'fixture-password-123'})
        self.assertEqual(local.post('/api/push/subscribe',base_url='http://192.168.0.219:3000',json={'subscription':self.sub},headers={'X-CSRF-Token':r.json['csrf']}).status_code,409)

    def test_assigned_recipient_only_dedupe_and_encrypted_payload_privacy(self):
        self.register();self.register('chai',subscription('chai'))
        cid=self.lead()
        self.assertEqual([r['user_id'] for r in self.jobs()],['grasi'])
        with database(self.app) as db:notify_created(db,cid,actor_id='admin')
        self.assertEqual(len(self.jobs()),1)
        self.assertTrue(self.dispatch());self.assertFalse(self.dispatch())
        self.assertEqual(self.jobs()[0]['state'],'sent')
        notice=json.loads(self.sent[0]['data'])
        self.assertEqual(notice['title'],'Novo lead no CRM')
        self.assertNotIn('Nome privado',self.sent[0]['data']);self.assertNotIn('5554999991234',self.sent[0]['data'])
        nid=notice['notice']
        self.assertEqual(self.get('grasi','/api/notifications/'+str(nid)).status_code,200)
        self.assertEqual(self.get('chai','/api/notifications/'+str(nid)).status_code,404)
        self.assertEqual(self.get('admin','/api/notifications/'+str(nid)).status_code,404)
        sent=[]
        class Session:
            def post(self,url,data,headers,**kw):
                sent.append((url,data,headers))
                r=requests.Response();r.status_code=201;return r
        args=dict(self.sent[0]);args['requests_session']=Session()
        webpush(**args)
        self.assertEqual(len(sent),1)
        self.assertNotIn(b'Novo lead',sent[0][1]);self.assertNotIn(b'Nome privado',sent[0][1])
        self.assertEqual(sent[0][2]['content-encoding'],'aes128gcm')
        self.assertTrue(any(k.lower()=='authorization' for k in sent[0][2]))

    def test_transfer_read_delete_and_inactive_cancel_before_send(self):
        for index,changed in enumerate(['transfer','read','deleted','inactive']):
            with self.subTest(changed=changed):
                self.register();cid=self.lead()
                nid=self.jobs()[-1]['notification_id']
                with database(self.app) as db:
                    if changed=='transfer':db.execute("UPDATE contacts SET owner_id='chai' WHERE id=?",(cid,))
                    if changed=='read':db.execute('UPDATE notifications SET read_at=? WHERE id=?',(time.time(),nid))
                    if changed=='deleted':db.execute('UPDATE contacts SET deleted_at=? WHERE id=?',(time.time(),cid))
                    if changed=='inactive':db.execute("UPDATE users SET active=0 WHERE id='grasi'")
                self.assertTrue(self.dispatch())
                self.assertEqual(self.jobs()[-1]['state'],'cancelled')
                self.assertEqual(self.sent,[])
                with database(self.app) as db:
                    db.execute('UPDATE contacts SET phone=phone||? WHERE id=?',(str(index),cid))
                    db.execute("UPDATE users SET active=1 WHERE id='grasi'")

    def test_new_device_has_no_backlog_and_endpoint_rebind_cancels_old_user(self):
        self.lead();self.register()
        self.assertEqual(self.jobs(),[])
        # Fresh event after registration; transfer to Chai should not send an old Grasi notice.
        with database(self.app) as db:
            row=db.execute('SELECT id FROM contacts').fetchone()
            db.execute("UPDATE contacts SET revision=revision+1 WHERE id=?",(row['id'],))
            from notifications import _push
            _push(db,row['id'],'assigned',['grasi'],'fixture-event')
        self.register('chai')
        self.assertEqual(self.jobs()[0]['state'],'cancelled')
        self.assertFalse(self.dispatch());self.assertEqual(self.sent,[])

    def test_expired_subscriptions_and_bounded_retry(self):
        self.register();self.lead()
        def failure(**kw):
            response=requests.Response();response.status_code=503
            raise WebPushException('provider details must not leak',response=response)
        self.app.config['PUSH_SENDER']=failure
        for i in range(4):
            self.assertTrue(self.dispatch())
            self.assertEqual(self.jobs()[0]['attempts'],i+1)
            if i<3:
                self.assertEqual(self.jobs()[0]['state'],'queued')
                self.assertGreater(self.jobs()[0]['next_try'],time.time())
                with database(self.app) as db:db.execute('UPDATE push_deliveries SET next_try=0')
        self.assertEqual(self.jobs()[0]['state'],'failed')
        self.assertEqual(self.jobs()[0]['last_error'],'http_503')
        with database(self.app) as db:db.execute("UPDATE push_deliveries SET state='queued',next_try=0,attempts=0")
        def expired(**kw):
            response=requests.Response();response.status_code=410
            raise WebPushException('expired',response=response)
        self.app.config['PUSH_SENDER']=expired
        self.dispatch();self.assertEqual(self.jobs()[0]['state'],'expired')
        with database(self.app) as db:self.assertEqual(db.execute('SELECT enabled FROM push_subscriptions').fetchone()[0],0)

    def test_test_is_delayed_rate_limited_and_unsubscribe_is_per_recipient(self):
        self.register()
        self.assertEqual(self.post('grasi','/api/push/test',{'endpoint':self.sub['endpoint']}).status_code,200)
        self.assertFalse(self.dispatch())
        self.assertEqual(self.post('grasi','/api/push/test',{'endpoint':self.sub['endpoint']}).status_code,429)
        self.assertEqual(self.post('chai','/api/push/test',{'endpoint':self.sub['endpoint']}).status_code,409)
        self.assertEqual(self.post('chai','/api/push/unsubscribe',{'endpoint':self.sub['endpoint']}).status_code,200)
        with database(self.app) as db:db.execute('UPDATE push_deliveries SET next_try=0')
        self.dispatch();self.assertEqual(self.jobs()[0]['state'],'sent')
        self.assertEqual(json.loads(self.sent[0]['data'])['title'],'Teste Sais Blue CRM')
        self.post('grasi','/api/push/unsubscribe',{'endpoint':self.sub['endpoint']})
        with database(self.app) as db:self.assertEqual(db.execute('SELECT enabled FROM push_subscriptions').fetchone()[0],0)


if __name__=='__main__': unittest.main()
