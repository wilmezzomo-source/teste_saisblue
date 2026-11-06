import hashlib
import hmac
import io
import json
import unittest
import urllib.error
import urllib.parse
from webhook_gateway import create_gateway,backend_url,probe_backend,OFFICIAL_PHONE_ID
from public_webhook_check import verify_public,callback_url
from configurar_meta_https import prepare,APP_ID


class Reply(io.BytesIO):
    status=200
    headers={'Content-Type':'application/json'}


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.values={'APP_URL':'http://192.168.0.219:3000','CRM_LISTEN_HOST':'192.168.0.219','META_PHONE_NUMBER_ID':OFFICIAL_PHONE_ID,'META_VERIFY_TOKEN':'verification-fixture','META_APP_SECRET':'app-secret-fixture'}
        self.requests=[]
        def send(req,timeout):
            self.requests.append(req)
            if req.get_method()=='GET':
                return Reply(urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)['hub.challenge'][0].encode())
            return Reply(b'{"ok":true}')
        self.client=create_gateway(self.values,send).test_client()

    def test_crm_routes_are_never_forwarded(self):
        for path in ['/','/login','/api/contacts','/api/status','/style.css']:
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.requests,[])

    def test_verification_preserves_challenge_and_strips_unrelated_inputs(self):
        self.assertEqual(self.client.get('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=bad&hub.challenge=123').status_code,403)
        response=self.client.get('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verification-fixture&hub.challenge=challenge123&extra=do-not-forward')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,b'challenge123')
        self.assertNotIn('extra',self.requests[0].full_url)

    def test_signature_raw_body_and_private_headers(self):
        raw=b'{ "entry": [], "unicode":"\\u00e7" }'
        self.assertEqual(self.client.post('/webhooks/whatsapp',data=raw).status_code,403)
        signature='sha256='+hmac.new(b'app-secret-fixture',raw,hashlib.sha256).hexdigest()
        response=self.client.post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature,'Cookie':'crm_session=private','Authorization':'Bearer private'})
        self.assertEqual(response.status_code,200)
        forwarded=self.requests[0]
        self.assertEqual(forwarded.data,raw)
        self.assertNotIn('Cookie',forwarded.headers)
        self.assertNotIn('Authorization',forwarded.headers)
        self.assertEqual(forwarded.full_url,'http://192.168.0.219:3000/webhooks/whatsapp')

    def test_backend_target_cannot_be_public(self):
        with self.assertRaises(ValueError):backend_url({**self.values,'CRM_LISTEN_HOST':'8.8.8.8'})
        with self.assertRaises(ValueError):create_gateway({**self.values,'META_PHONE_NUMBER_ID':'test-number'})

    def test_backend_preflight_does_not_create_messages(self):
        calls=[]
        def sender(req,timeout):
            if isinstance(req,str):
                query=urllib.parse.parse_qs(urllib.parse.urlsplit(req).query)
                return Reply(query['hub.challenge'][0].encode())
            calls.append(req)
            self.assertEqual(json.loads(req.data)['entry'],[])
            return Reply(b'{"ok":true}')
        self.assertEqual(probe_backend(self.values,sender),'http://192.168.0.219:3000')
        self.assertEqual(len(calls),1)

    def test_public_check_validates_challenge_and_isolation_without_meta_access_token(self):
        def sender(req,timeout):
            self.assertNotIn('Authorization',req.headers)
            parsed=urllib.parse.urlsplit(req.full_url)
            if parsed.path=='/webhooks/whatsapp':
                return Reply(urllib.parse.parse_qs(parsed.query)['hub.challenge'][0].encode())
            raise urllib.error.HTTPError(req.full_url,404,'not found',{},None)
        self.assertEqual(verify_public('https://example.ngrok-free.app','fixture-verifier',sender),'https://example.ngrok-free.app/webhooks/whatsapp')
        for url in ['http://example.test','https://user:password@example.test','https://example.test/?token=secret']:
            with self.assertRaises(ValueError):callback_url(url)
        def exposed(req,timeout):
            if '/webhooks/whatsapp?' in req.full_url:
                return sender(req,timeout)
            return Reply(b'private app')
        with self.assertRaisesRegex(ValueError,'aplicação inteira'):
            verify_public('https://example.ngrok-free.app','fixture-verifier',exposed)

    def test_setup_confirms_both_official_phone_and_app_secret_before_saving(self):
        def sender(req,timeout):
            if '/'+OFFICIAL_PHONE_ID+'?' in req.full_url:
                return Reply(b'{"display_phone_number":"+55 54 3443-6405"}')
            self.assertEqual(req.headers['Authorization'],'Bearer '+APP_ID+'|fixture-app-secret')
            return Reply(json.dumps({'id':APP_ID,'name':'Sais Blue CRM'}).encode())
        values=prepare({'CRM_DB':'data/existing.db','APP_URL':'http://192.168.0.219:3000'},'meta-fixture','fixture-app-secret','ngrok-fixture',sender)
        self.assertEqual(values['CRM_DB'],'data/existing.db')
        self.assertEqual(values['APP_URL'],'http://192.168.0.219:3000')
        self.assertEqual(values['META_PHONE_NUMBER_ID'],OFFICIAL_PHONE_ID)
        self.assertTrue(values['META_VERIFY_TOKEN'])

    def test_real_backend_receives_ad_lead_and_deduplicates_through_gateway(self):
        import tempfile
        from server import create_app,database
        with tempfile.TemporaryDirectory() as directory:
            backend=create_app({'TESTING':True,'DATABASE':directory+'/crm.db','META_APP_SECRET':'app-secret-fixture','META_VERIFY_TOKEN':'verification-fixture','META_PHONE_NUMBER_ID':OFFICIAL_PHONE_ID})
            private=backend.test_client()
            def sender(req,timeout):
                parsed=urllib.parse.urlsplit(req.full_url)
                result=private.open(parsed.path+('?'+parsed.query if parsed.query else ''),method=req.get_method(),data=req.data,headers=dict(req.header_items()))
                reply=Reply(result.data);reply.status=result.status_code;reply.headers=result.headers
                return reply
            public=create_gateway(self.values,sender).test_client()
            payload={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':OFFICIAL_PHONE_ID},'contacts':[{'wa_id':'5511999998888','profile':{'name':'Cliente do anúncio'}}],'messages':[{'id':'wamid.gateway.1','from':'5511999998888','type':'text','text':{'body':'Olá! Vim do anúncio.'},'referral':{'source_type':'ad','source_id':'campaign-fixture','headline':'Anúncio Sais Blue'}}]}}]}]}
            raw=json.dumps(payload,ensure_ascii=False).encode()
            signature='sha256='+hmac.new(b'app-secret-fixture',raw,hashlib.sha256).hexdigest()
            for _ in range(2):
                self.assertEqual(public.post('/webhooks/whatsapp',data=raw,headers={'X-Hub-Signature-256':signature}).status_code,200)
            with database(backend) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],1)
                row=db.execute('SELECT * FROM contacts').fetchone()
                self.assertEqual(row['source'],'Anúncio Meta')
                self.assertEqual(row['city_id'],'')
                self.assertEqual(json.loads(row['referral'])['source_id'],'campaign-fixture')

    def test_tunnel_selection_never_uses_crm_port(self):
        from iniciar_https import tunnel_url
        def sender(url,timeout):
            return Reply(json.dumps({'tunnels':[{'config':{'addr':'http://192.168.0.219:3000'},'public_url':'https://wrong.ngrok-free.app'},{'config':{'addr':'http://127.0.0.1:3002'},'public_url':'https://right.ngrok-free.app'}]}).encode())
        self.assertEqual(tunnel_url(sender),'https://right.ngrok-free.app')
