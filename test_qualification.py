import hashlib
import hmac
import io
import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from qualification import parse_city, routing_group, REMINDER_DELAYS, FINAL_REMINDER_AFTER
from unittest.mock import patch
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
            self.assertEqual(db.execute('SELECT COUNT(*) FROM notifications').fetchone()[0],0)
        self.receive('Mensagem do anúncio',ad=True)
        self.receive('Resposta sem referral')
        c=self.contact()
        self.assertEqual(c['ad_origin'],1)
        self.assertEqual(c['source'],'Anúncio Meta')
        self.assertEqual(len(c['messages']),2)
        self.assertEqual(self.post('/api/contacts',{'name':'Manual','phone':'5554999992222'}).status_code,400)

    def test_manual_opportunity_admits_only_its_future_messages_without_bot(self):
        self.enable()
        member = self.app.test_client()
        csrf = member.post('/api/login', json={'email':'chai@example.test','password':'fixture-password-123'}).json['csrf']
        fields = {'name':'Cliente cadastrado pela equipe','phone':'+55 (54) 99999-2222',
                  'city_id':'4309407','lead_profile':'Revenda','owner_id':'chai','value':'1750.50',
                  'stage':'Negociação','instagram':'@saisblue','note':'Indicação de cliente',
                  'source':'Anúncio Meta','ad_origin':1,'manual_origin':0,'qualification_state':'waiting_profile'}
        result = member.post('/api/contacts', json=fields, headers={'X-CSRF-Token':csrf})
        self.assertEqual(result.status_code,201,result.json)
        c = self.contact('5554999992222')
        self.assertEqual((c['source'],c['ad_origin'],c['manual_origin'],c['qualification_state']),('Manual',0,1,'human'))
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner'],c['value'],c['stage']),('Revenda','Guaporé','RS','Chai',1750.5,'Negociação'))
        self.assertEqual(c['instagram'],'saisblue')
        self.assertEqual(c['messages'],[])
        self.assertEqual(c['audit'][0]['actor'],'Chai')
        # A manually typed phone never fabricates a WhatsApp service window.
        self.assertEqual(self.post('/api/send',{'id':c['id'],'body':'Olá','request_id':'a'*32}).status_code,409)
        self.receive('Nova mensagem do cliente',number='5554999992222')
        self.receive('Conversa comum de outro telefone',number='5554999993333')
        self.drain()
        self.assertEqual([m['body'] for m in self.contact('5554999992222')['messages']],['Nova mensagem do cliente'])
        self.assertEqual(self.sent,[])
        self.assertEqual(len(self.client.get('/api/contacts').json['contacts']),1)
        # A later ad click must not restart the bot over the human's manual admission.
        self.receive('Agora cliquei no anúncio',ad=True,number='5554999992222'); self.drain()
        self.assertEqual(self.contact('5554999992222')['qualification_state'],'human')
        self.assertEqual(self.sent,[])

    def test_manual_opportunity_validation_and_duplicate_preserve_existing_card(self):
        base = {'name':'Manual','phone':'5554999992222','city_id':'4309407'}
        for changes in ({'name':''},{'phone':''},{'city_id':''},{'city_id':'invalid'},
                        {'lead_profile':'Outro'},{'value':'nan'},{'value':-1},
                        {'stage':'Inválida'},{'owner':'Conta inexistente'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post('/api/contacts',dict(base,**changes)).status_code,400)
        self.assertEqual(self.post('/api/contacts',base).status_code,201)
        duplicate = self.post('/api/contacts',dict(base,name='Não deve substituir',phone='+55 (54) 99999-2222'))
        self.assertEqual(duplicate.status_code,409)
        self.assertEqual(self.contact()['name'],'Manual')
        self.receive('Oi',ad=True,number='5554999991111')
        duplicate_ad = self.post('/api/contacts',dict(base,phone='5554999991111'))
        self.assertEqual(duplicate_ad.status_code,409)
        self.assertEqual(self.contact('5554999991111')['manual_origin'],0)

    def test_manual_admission_is_explicit_and_preserved_after_restart(self):
        self.enable()
        self.post('/api/contacts',{'name':'Manual','phone':'5554999992222','city_id':'4309407'})
        with database(self.app) as db:
            db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated) VALUES('old','Histórico','5554999993333','Novo contato','Manual',1,1)")
        restarted = create_app(dict(self.app.config))
        with database(restarted) as db:
            self.assertEqual(db.execute("SELECT manual_origin FROM contacts WHERE id='old'").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT manual_origin FROM contacts WHERE phone='5554999992222'").fetchone()[0],1)
            self.assertTrue(json.loads(db.execute("SELECT value FROM crm_settings WHERE key='qualification'").fetchone()[0])['enabled'])
        self.receive('Mensagem do contato histórico sem admissão',number='5554999993333')
        self.assertEqual(self.contact('5554999993333')['messages'],[])

    def test_all_profiles_and_state_routing_with_confirmed_city(self):
        self.enable()
        for i,(profile,city,state) in enumerate((p,city,uf) for p in ('Lojista','Revenda','Consumidor Final') for city,uf in [('Guaporé','RS'),('Florianópolis','SC'),('São Paulo','SP')]):
            with self.subTest(profile=profile,state=state):
                number=f'551199999{1000+i}'
                self.receive('Vim do anúncio',ad=True,number=number); self.drain()
                self.receive(profile,number=number); self.drain()
                self.receive(city+'/'+state,number=number); self.drain()
                c=self.contact(number)
                expected='Chai' if profile=='Lojista' or (profile=='Revenda' and state in ('RS','SC')) else 'Grasi'
                self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner']),(profile,city,state,expected))
                self.assertEqual(c['owner_id'],expected.lower())
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
        self.assertEqual(self.client.get('/api/notifications').json['unread'],1)

    def test_alert_waits_for_qualification_before_reaching_the_attendant_and_keeps_corrected_name(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        c = self.contact()
        self.assertTrue(c['location_pending'])
        self.assertEqual(self.post('/api/update',{'id':c['id'],'revision':c['revision'],'name':'Nome real confirmado'}).status_code,200)
        self.assertEqual(self.client.get('/api/notifications').json['notifications'][0]['name'],'Nome real confirmado')
        with database(self.app) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notifications WHERE user_id IN ('chai','grasi')").fetchone()[0],0)
        self.receive('Revenda');self.drain()
        self.receive('Guaporé/RS');self.drain()
        self.assertEqual(self.contact()['name'],'Nome real confirmado')
        chai = self.app.test_client()
        chai.post('/api/login',json={'email':'chai@example.test','password':'fixture-password-123'})
        data = chai.get('/api/notifications').json
        self.assertEqual(data['unread'],1)
        self.assertEqual(data['notifications'][0]['name'],'Nome real confirmado')
        self.assertEqual(data['notifications'][0]['kind'],'assigned')

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
        self.assertEqual(c['qualification_state'],'completed')
        self.assertEqual((c['city'],c['state'],c['owner']),('Guaporé','RS','Chai'))

    def test_request_person_and_manual_handoff_stop_questions_without_location(self):
        self.enable();self.receive('Oi',ad=True)
        c=self.contact()
        result=self.post('/api/claim',{'id':c['id'],'revision':c['revision'],'owner':'Grasi'})
        self.assertEqual(result.status_code,200,result.json)
        self.drain();self.receive('1');self.drain()
        c=self.contact()
        self.assertEqual(c['owner'],'Grasi')
        self.assertEqual(c['stage'],'Novo contato')
        self.assertEqual(c['qualification_state'],'human')
        self.assertEqual(len(self.sent),0)
        self.receive('Quero falar com uma pessoa',ad=True,number='5554999992222');self.drain()
        self.assertEqual(self.contact('5554999992222')['qualification_state'],'waiting_profile')
        self.assertEqual(len(self.sent),1)
        self.assertNotIn('ATENDENTE',self.sent[0]['text']['body'])

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

    def test_delete_cancels_qualification_and_ignores_new_messages_until_restored(self):
        self.enable(); self.receive('Oi',ad=True)
        c = self.contact()
        self.assertEqual(self.post('/api/contacts/delete',{'id':c['id'],'revision':c['revision']}).status_code,200)
        self.drain()
        self.receive('Novo clique no anúncio',ad=True)
        self.drain()
        self.assertEqual(self.sent,[])
        self.assertEqual(self.client.get('/api/contacts').json['contacts'],[])
        with database(self.app) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM messages WHERE direction='in'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT status FROM messages WHERE automation=1").fetchone()[0],'cancelled')
        deleted = self.client.get('/api/trash').json['contacts'][0]
        self.assertEqual(self.post('/api/contacts/restore',{'id':c['id'],'revision':deleted['revision']}).status_code,200)
        self.receive('Retomar com uma pessoa')
        self.drain()
        self.assertEqual(self.contact()['qualification_state'],'human')
        self.assertEqual(self.sent,[])

    def progress(self):
        with database(self.app) as db:
            return dict(db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(self.contact()['id'],)).fetchone())

    def test_many_separate_messages_preserve_location_and_do_not_abandon(self):
        self.enable(); self.receive('Oi',ad=True);self.drain()
        for body in ['bom dia','tudo bem?','atendente','eu gostaria de saber mais','Sou uma lojista']:
            self.receive(body);self.drain()
        self.assertEqual(self.contact()['qualification_state'],'waiting_city')
        self.receive('Guaporé');self.drain()
        self.receive('só um momento');self.drain()
        restarted=create_app(dict(self.app.config))
        self.assertFalse(run_automation_once(restarted))
        self.receive('Rio Grande do Sul');self.drain()
        c=self.contact()
        self.assertEqual((c['qualification_state'],c['city'],c['state'],c['owner'],c['stage']),('completed','Guaporé','RS','Chai','Novo contato'))
        self.assertTrue(all('ATENDENTE' not in m['text']['body'] for m in self.sent))
        self.assertEqual(self.progress()['next_due'],0)

    def test_state_and_city_before_profile_and_wrong_pair_can_be_corrected(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        for body in ['UF SC','Guaporé','sou revendedora','RS']:
            self.receive(body);self.drain()
        self.assertEqual((self.contact()['city'],self.contact()['state'],self.contact()['owner']),('Guaporé','RS','Chai'))
        self.receive('Oi',ad=True,number='5554999994444');self.drain()
        for body in ['SP','São Paulo','uso próprio']:
            self.receive(body,number='5554999994444');self.drain()
        c=self.contact('5554999994444')
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner']),('Consumidor Final','São Paulo','SP','Grasi'))

    def test_reminder_intervals_final_cutoff_and_restart_deduplication(self):
        self.enable()
        anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):
            self.receive('Oi',ad=True,timestamp=anchor);self.drain()
            due=self.progress()['next_due']
            self.assertAlmostEqual(due,anchor+300,delta=2)
        previous=anchor
        for index,delay in enumerate(REMINDER_DELAYS):
            with self.subTest(index=index):
                self.assertAlmostEqual(due-previous,delay,delta=2)
                with patch('qualification.time.time',return_value=due-.01):self.assertFalse(run_automation_once(self.app))
                restarted=create_app(dict(self.app.config))
                with patch('qualification.time.time',return_value=due):
                    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:run_automation_once(restarted),range(3)))
                    self.drain()
                    self.assertEqual(len(self.sent),index+2)
                    progress=self.progress();self.assertEqual(progress['reminders_sent'],index+1)
                    previous,due=due,progress['next_due']
        self.assertAlmostEqual(due,anchor+FINAL_REMINDER_AFTER,delta=2)
        with patch('qualification.time.time',return_value=due):self.drain();self.drain()
        self.assertEqual(len(self.sent),6)
        self.assertEqual(self.progress()['closed_reason'],'finished')
        self.assertEqual(self.contact()['stage'],'Novo contato')
        with patch('qualification.time.time',return_value=anchor+90000):self.drain()
        self.assertEqual(len(self.sent),6)
        self.assertTrue(all(m['type']=='text' for m in self.sent))

    def test_reply_cancels_queued_reminder_and_restarts_for_only_missing_fields(self):
        self.enable();anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):
            self.receive('Oi',ad=True,timestamp=anchor);self.drain()
        with patch('qualification.time.time',return_value=anchor+301):
            from qualification import schedule_reminder
            from server import audit
            with self.app.app_context(),database(self.app) as db:schedule_reminder(db,audit)
        with patch('qualification.time.time',return_value=anchor+302):
            self.receive('Revenda',timestamp=anchor+302);self.drain()
            self.assertEqual(len(self.sent),2)
            self.assertAlmostEqual(self.progress()['next_due'],anchor+602,delta=2)
            self.assertEqual(self.progress()['reminders_sent'],0)
            self.assertIn('cidade',self.sent[-1]['text']['body'])
        with database(self.app) as db:
            self.assertEqual(db.execute("SELECT status FROM messages WHERE automation_kind='reminder'").fetchone()[0],'cancelled')

    def test_no_burst_after_downtime_and_no_messages_outside_24_hours(self):
        self.enable();anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):self.receive('Oi',ad=True,timestamp=anchor);self.drain()
        with patch('qualification.time.time',return_value=anchor+5*3600):
            self.drain();self.drain()
            self.assertEqual(len(self.sent),2)
            self.assertAlmostEqual(self.progress()['next_due'],anchor+5*3600+600,delta=2)
        with patch('qualification.time.time',return_value=anchor+86401):self.drain()
        self.assertEqual(len(self.sent),2)
        self.assertEqual(self.progress()['closed_reason'],'window_closed')
        self.assertEqual(self.contact()['qualification_state'],'waiting_profile')
        with patch('qualification.time.time',return_value=anchor+86402):
            self.receive('Lojista',timestamp=anchor+86402);self.drain()
            self.client.post('/api/login',json={'email':'admin@example.test','password':'fixture-password-123'})
            self.assertEqual(self.contact()['qualification_state'],'waiting_city')
            self.assertEqual(len(self.sent),3)

    def test_finished_optout_claim_and_disabled_automation_cancel_reminders(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        self.receive('SAIR');self.drain()
        count=len(self.sent)
        with patch('qualification.time.time',return_value=time.time()+10000):self.drain()
        self.assertEqual(len(self.sent),count)
        self.assertEqual(self.progress()['next_due'],0)
        self.assertEqual(self.contact()['qualification_state'],'human')
        self.receive('não quero receber mensagens',ad=True,number='5554999994444');self.drain()
        self.assertEqual(self.contact('5554999994444')['qualification_state'],'human')


    def test_shopkeeper_rule_covers_every_state_and_other_profiles_keep_regional_rule(self):
        from qualification import STATE_NAMES
        for state in STATE_NAMES:
            self.assertEqual(routing_group('Lojista',state),'chai')
            self.assertEqual(routing_group('Revenda',state),'chai' if state in ('RS','SC') else 'grasi')
            self.assertEqual(routing_group('Consumidor Final',state),'grasi')

    def test_migration_reassigns_open_ad_shopkeepers_once_without_changing_columns(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        self.receive('Lojista');self.drain();self.receive('São Paulo/SP');self.drain()
        cid=self.contact()['id']
        with database(self.app) as db:
            db.execute("DELETE FROM crm_settings WHERE key='qualification_rules_20261109_6'")
            db.execute("UPDATE contacts SET owner_id='grasi',owner='Grasi',stage='Em atendimento' WHERE id=?",(cid,))
        self.drain()
        self.assertEqual((self.contact()['owner_id'],self.contact()['stage']),('chai','Em atendimento'))
        with database(self.app) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE action='Regra de Lojista aplicada'").fetchone()[0],1)
            db.execute("UPDATE contacts SET owner_id='grasi',owner='Grasi' WHERE id=?",(cid,))
        self.drain()  # A later explicit admin transfer must not be reversed on every tick.
        self.assertEqual(self.contact()['owner_id'],'grasi')

    def test_legacy_two_invalid_answers_resume_with_saved_history_but_human_claims_do_not(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        self.receive('Revenda');self.drain();self.receive('Guaporé');self.drain()
        self.receive('RS');self.drain()
        cid=self.contact()['id']
        with database(self.app) as db:
            db.execute("DELETE FROM crm_settings WHERE key='qualification_rules_20261109_6'")
            db.execute('DELETE FROM qualification_progress WHERE contact_id=?',(cid,))
            db.execute("UPDATE contacts SET qualification_state='human',qualification_attempts=2,city_id='',city='',state='',owner_id='',owner='Sem responsável' WHERE id=?",(cid,))
            db.execute("INSERT INTO audit(contact_id,actor,action,details,created) VALUES(?,'Assistente Sais Blue','Qualificação encaminhada à equipe',?,?)",(cid,json.dumps({'motivo':'Respostas não identificadas; conferir os campos pendentes'}),time.time()))
        self.drain()
        c=self.contact()
        self.assertEqual((c['qualification_state'],c['city'],c['state'],c['owner_id']),('completed','Guaporé','RS','chai'))
        self.assertEqual(c['stage'],'Novo contato')


    def test_shopkeeper_migration_does_not_reassign_manual_cards_other_profiles_or_closed_sales(self):
        self.enable()
        cases=[('manual','Lojista','Novo contato',1),('revenda','Revenda','Novo contato',0),('consumer','Consumidor Final','Novo contato',0),('won','Lojista','Ganho',0)]
        with database(self.app) as db:
            for i,(cid,profile,stage,manual) in enumerate(cases):
                db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated,owner,owner_id,lead_profile,ad_origin,manual_origin,qualification_state,city_id) VALUES(?,?,?,?,?,1,1,'Grasi','grasi',?,1,?,'completed','3550308')",(cid,cid,'555499999'+str(1000+i),stage,'fixture',profile,manual))
        self.drain()
        self.assertTrue(all(c['owner_id']=='grasi' for c in self.client.get('/api/contacts').json['contacts']))



if __name__ == '__main__':
    unittest.main()
