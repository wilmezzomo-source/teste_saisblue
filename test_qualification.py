import hashlib
import hmac
import io
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from qualification import parse_city, routing_group
from server import create_app, database, password, run_automation_once


class QualificationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.sent = []
        def sender(req, timeout):
            self.sent.append(json.loads(req.data))
            return io.BytesIO(json.dumps({'messages':[{'id':f'out.{len(self.sent)}'}]}).encode())
        self.app = create_app({'TESTING':True,'DATABASE':self.temp.name+'/crm.db','APP_URL':'',
                               'META_APP_SECRET':'fixture-secret','META_VERIFY_TOKEN':'fixture-verify',
                               'META_PHONE_NUMBER_ID':'official-fixture','META_ACCESS_TOKEN':'fixture-token',
                               'META_SENDER':sender,'ALLOW_SIMULATION':False,'SECURE_COOKIE':False})
        with database(self.app) as db:
            hashed = password('fixture-password-123')
            for uid, name, role in [('admin','Willian','admin'),('chai','Chai','member'),('grasi','Grasi','member')]:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',(uid,uid+'@example.test',name,hashed,role,time.time()))
        self.client = self.app.test_client()
        self.csrf = self.client.post('/api/login',json={'email':'admin@example.test','password':'fixture-password-123'}).json['csrf']
        self.serial = 0

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, fields):
        return self.client.post(path,json=fields,headers={'X-CSRF-Token':self.csrf})

    def enable(self):
        result=self.post('/api/automation',{'enabled':True,'assignment_mode':'regional','regional_owners':{'chai':'chai','grasi':'grasi'}})
        self.assertEqual(result.status_code,200,result.json)

    def payload(self, body='Olá', ad=False, number='5554999991111', timestamp=None):
        self.serial += 1
        m={'id':f'in.{self.serial}','from':number,'type':'text','text':{'body':body},'timestamp':str(timestamp or time.time())}
        if ad:
            m['referral']={'source_type':'ad','source_id':'fixture-ad','ctwa_clid':'fixture-click'}
        return {'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'official-fixture'},'contacts':[{'wa_id':number,'profile':{'name':'Lead fixture'}}],'messages':[m]}}]}]}

    def signed(self, payload):
        raw=json.dumps(payload).encode()
        signature='sha256='+hmac.new(b'fixture-secret',raw,hashlib.sha256).hexdigest()
        result=self.app.test_client().post('/webhooks/whatsapp',data=raw,content_type='application/json',headers={'X-Hub-Signature-256':signature})
        self.assertEqual(result.status_code,200,result.json)
        return result

    def receive(self, body, **kwargs):
        self.signed(self.payload(body,**kwargs))

    def drain(self):
        for _ in range(30):
            if not run_automation_once(self.app): return
        self.fail('Outbox did not drain')

    def contact(self, number=None):
        rows=self.client.get('/api/contacts').json['contacts']
        return next(c for c in rows if number is None or c['phone']==number)

    def test_only_verified_ads_admit_new_contacts_and_continuations_survive(self):
        self.receive('Vim do anúncio, sou cliente!')
        post=self.payload()
        post['entry'][0]['changes'][0]['value']['messages'][0]['referral']={'source_type':'post','source_id':'post-fixture'}
        self.signed(post)
        missing_type=self.payload()
        missing_type['entry'][0]['changes'][0]['value']['messages'][0]['referral']={'source_id':'unknown'}
        self.signed(missing_type)
        with database(self.app) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
        self.receive('Mensagem do anúncio',ad=True)
        self.receive('Resposta sem referral')
        c=self.contact()
        self.assertEqual(c['ad_origin'],1)
        self.assertEqual(c['source'],'Anúncio Meta')
        self.assertEqual(len(c['messages']),2)
        self.assertEqual(self.post('/api/contacts',{'name':'Manual','phone':'5554999992222'}).status_code,403)

    def test_all_profiles_and_state_routing_with_confirmed_city(self):
        self.enable()
        for i,(profile,city,state) in enumerate((p,city,uf) for p in ('Lojista','Revenda','Consumidor Final') for city,uf in [('Guaporé','RS'),('Florianópolis','SC'),('São Paulo','SP')]):
            with self.subTest(profile=profile,state=state):
                number=f'551199999{1000+i}'
                self.receive('Vim do anúncio',ad=True,number=number); self.drain()
                self.receive(profile,number=number); self.drain()
                self.receive(city+'/'+state,number=number); self.drain()
                c=self.contact(number)
                expected='Chai' if profile!='Consumidor Final' and state in ('RS','SC') else 'Grasi'
                self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner']),(profile,city,state,expected))
                self.assertFalse(c['location_pending'])
                self.assertEqual(c['qualification_state'],'completed')
                self.assertEqual(len([m for m in c['messages'] if m['automation']]),3)
                self.receive('Obrigado',number=number); self.drain()
                self.assertEqual(len([m for m in self.contact(number)['messages'] if m['automation']]),3)

    def test_duplicate_webhooks_and_competing_workers_send_one_question(self):
        self.enable()
        payload=self.payload(ad=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _:self.signed(payload),range(3)))
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _:run_automation_once(self.app),range(3)))
        self.assertEqual(len(self.sent),1)
        self.assertEqual(len(self.contact()['messages']),2)

    def test_location_is_exact_and_ambiguous_or_wrong_state_is_not_guessed(self):
        for value in ('Guapore/RS','Guaporé - RS','Sou de Guaporé Rio Grande do Sul'):
            self.assertEqual(parse_city(value)['name'],'Guaporé')
        for value in ('Guaporé','Guaporé/SC','São Paulo/RS','RS','em algum lugar','Guaporé/XX'):
            self.assertIsNone(parse_city(value))
        self.enable(); self.receive('Oi',ad=True);self.drain()
        self.receive('1'); self.drain()
        self.receive('Guaporé');self.drain()
        self.receive('RS');self.drain()
        c=self.contact()
        self.assertEqual(c['qualification_state'],'human')
        self.assertEqual(c['city_id'],'')
        self.assertEqual(c['owner'],'Sem responsável')

    def test_request_person_and_manual_handoff_stop_questions_without_location(self):
        self.enable();self.receive('Oi',ad=True)
        c=self.contact()
        result=self.post('/api/claim',{'id':c['id'],'revision':c['revision'],'owner':'Grasi'})
        self.assertEqual(result.status_code,200,result.json)
        self.drain();self.receive('1');self.drain()
        c=self.contact()
        self.assertEqual(c['owner'],'Grasi')
        self.assertEqual(c['qualification_state'],'human')
        self.assertEqual(len(self.sent),0)
        self.receive('Quero falar com uma pessoa',ad=True,number='5554999992222');self.drain()
        self.assertEqual(self.contact('5554999992222')['qualification_state'],'human')
        self.assertEqual(len(self.sent),0)

    def test_timeout_is_recorded_once_and_delegated_without_retry(self):
        self.enable();self.receive('Oi',ad=True)
        def timeout(req,timeout):
            self.sent.append('timeout')
            raise TimeoutError()
        self.app.config['META_SENDER']=timeout
        self.drain();self.drain()
        c=self.contact()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(c['qualification_state'],'human')
        self.assertEqual(next(m for m in c['messages'] if m['automation'])['status'],'uncertain')

    def test_expired_inbound_and_queued_messages_never_open_a_new_window(self):
        self.enable();self.receive('Antiga',ad=True,timestamp=time.time()-90000);self.drain()
        self.assertEqual(len(self.sent),0)
        self.receive('Atual');
        with database(self.app) as db:
            db.execute("UPDATE messages SET created=? WHERE direction='in'",(time.time()-90000,))
        self.drain()
        self.assertEqual(len(self.sent),0)

    def test_configuration_requires_admin_and_active_routing_accounts(self):
        self.assertEqual(self.post('/api/automation',{'enabled':True,'assignment_mode':'regional'}).status_code,400)
        self.enable();self.receive('Olá',ad=True)
        self.assertEqual(self.post('/api/automation',{'enabled':False}).status_code,200)
        self.drain()
        self.assertEqual(len(self.sent),0)
        self.assertEqual(self.contact()['qualification_state'],'human')
        member=self.app.test_client()
        csrf=member.post('/api/login',json={'email':'chai@example.test','password':'fixture-password-123'}).json['csrf']
        self.assertEqual(member.post('/api/automation',json={'enabled':True},headers={'X-CSRF-Token':csrf}).status_code,403)

    def test_delivery_failure_after_acceptance_is_visible_and_not_retried(self):
        self.enable();self.receive('Olá',ad=True);self.drain()
        payload={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'official-fixture'},'statuses':[{'id':'out.1','status':'failed','errors':[{'code':131000}]}]}}]}]}
        self.signed(payload);self.drain()
        c=self.contact()
        self.assertEqual(c['qualification_state'],'human')
        m=next(m for m in c['messages'] if m['automation'])
        self.assertEqual((m['status'],m['error_code']),('failed',131000))
        self.assertEqual(len(self.sent),1)

    def test_saved_outbox_survives_restart_and_does_not_resend_accepted_messages(self):
        self.enable();self.receive('Olá',ad=True)
        restarted=create_app(dict(self.app.config))
        self.assertTrue(run_automation_once(restarted))
        self.assertFalse(run_automation_once(restarted))
        self.assertEqual(len(self.sent),1)
        self.receive('1')
        with database(self.app) as db:
            db.execute("UPDATE messages SET status='sending',send_started=? WHERE status='queued'", (time.time()-200,))
        self.drain()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.contact()['qualification_state'],'human')

    def test_earlier_messages_do_not_answer_the_current_question(self):
        self.enable();t=time.time()-10
        self.receive('Olá',ad=True,timestamp=t);self.drain()
        self.receive('1',timestamp=t+5);self.drain()
        self.receive('São Paulo/SP',timestamp=t+1);self.drain()
        c=self.contact()
        self.assertEqual(c['qualification_state'],'waiting_city')
        self.assertTrue(c['location_pending'])

    def test_removed_stage_migrates_to_negotiation_once_preserving_card(self):
        self.receive('Olá',ad=True)
        c=self.contact()
        with database(self.app) as db:
            db.execute("UPDATE contacts SET stage='Proposta enviada',value=1500,owner='Chai' WHERE id=?",(c['id'],))
        migrated=create_app(dict(self.app.config))
        with database(migrated) as db:
            row=dict(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone())
            self.assertEqual((row['stage'],row['value'],row['owner']),('Negociação',1500,'Chai'))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],1)
        restarted=create_app(dict(self.app.config))
        with database(restarted) as db:
            self.assertEqual(db.execute('SELECT revision FROM contacts WHERE id=?',(c['id'],)).fetchone()[0],row['revision'])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE action='Etapa removida do funil'").fetchone()[0],1)


if __name__ == '__main__':
    unittest.main()
