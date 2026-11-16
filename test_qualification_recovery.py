import time
import unittest

import test_qualification as fixtures
from qualification import handover
from server import database, audit, create_app, start_automation_worker


class RecoveryTest(unittest.TestCase):
    setUp=fixtures.QualificationTest.setUp
    tearDown=fixtures.QualificationTest.tearDown
    post=fixtures.QualificationTest.post
    enable=fixtures.QualificationTest.enable
    payload=fixtures.QualificationTest.payload
    signed=fixtures.QualificationTest.signed
    receive=fixtures.QualificationTest.receive
    drain=fixtures.QualificationTest.drain
    contact=fixtures.QualificationTest.contact

    def recover(self):
        response=self.post('/api/automation/recover',{})
        self.assertEqual(response.status_code,200,response.json)
        return response.json['report']

    def pause(self,status='failed',reason='Credenciais de envio indisponíveis'):
        cid=self.contact()['id']
        with self.app.app_context(),database(self.app) as db:
            db.execute('UPDATE messages SET status=? WHERE contact_id=? AND direction=\'out\'',(status,cid))
            handover(db,cid,audit,reason)

    def test_stored_unanswered_ad_resumes_once_without_external_crm_access(self):
        self.receive('Quero começar a revender',ad=True)
        self.enable()
        self.assertEqual(self.recover()['prepared'],1);self.drain()
        self.assertEqual(len(self.sent),1)
        self.assertIn('cidade',self.sent[0]['text']['body'])
        self.assertEqual(self.recover()['already_attempted'],1);self.drain()
        self.assertEqual(len(self.sent),1)
        status=self.client.get('/api/automation/recovery').json['recovery']['sends']
        self.assertEqual(status['accepted'],1);self.assertEqual(status.get('delivered',0),0)

    def test_startup_worker_prepares_and_sends_existing_pending_message(self):
        self.receive('Para meu uso',ad=True);self.enable()
        stop,worker=start_automation_worker(self.app)
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if self.sent and self.client.get('/api/automation/recovery').json['recovery']['sends'].get('accepted'):break
                time.sleep(.02)
            self.assertEqual(len(self.sent),1)
            self.assertEqual(self.contact()['lead_profile'],'Consumidor Final')
        finally:
            stop.set();worker.join(timeout=3)

    def test_pending_queue_and_accepted_reply_are_not_duplicated(self):
        self.enable();self.receive('Oi',ad=True)
        self.assertEqual(self.recover()['already_queued'],1)
        self.drain();self.assertEqual(len(self.sent),1)
        self.assertEqual(self.recover()['already_answered'],1);self.drain()
        self.assertEqual(len(self.sent),1)

    def test_previously_answered_lead_is_excluded_even_with_a_new_unanswered_reply(self):
        self.enable();self.receive('Oi',ad=True);self.drain()
        with database(self.app) as db:
            c=self.contact()
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel,external_id) VALUES('new-unanswered',?,'Quero revender','in',?,'meta','new-unanswered')",(c['id'],time.time()))
        self.assertEqual(self.recover()['already_answered'],1);self.drain()
        self.assertEqual(len(self.sent),1)

    def test_certain_failure_can_resume_but_another_restart_does_not_retry_it(self):
        self.enable();self.receive('Revenda',ad=True);self.pause()
        self.assertEqual(self.recover()['prepared'],1);self.drain()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.contact()['qualification_state'],'waiting_city')
        restarted=create_app(dict(self.app.config))
        stop,worker=start_automation_worker(restarted)
        try:
            time.sleep(.1)
            self.assertEqual(len(self.sent),1)
        finally:stop.set();worker.join(timeout=3)

    def test_ambiguous_and_inflight_send_need_review_and_are_not_retried(self):
        self.enable();self.receive('Oi',ad=True);self.pause('uncertain','Envio interrompido; conferir histórico antes de reenviar')
        self.assertEqual(self.recover()['uncertain'],1);self.drain()
        self.assertEqual(self.sent,[])
        with database(self.app) as db:db.execute("UPDATE messages SET status='sending',send_started=? WHERE direction='out'",(time.time(),))
        self.assertEqual(self.recover()['uncertain'],1)

    def test_manual_takeover_and_optout_are_preserved(self):
        self.enable();self.receive('Oi',ad=True);self.pause(reason='Cliente pediu para interromper mensagens automáticas')
        self.assertEqual(self.recover()['human'],1);self.assertEqual(self.sent,[])
        number='5554999992222';self.receive('Oi',ad=True,number=number)
        c=self.contact(number)
        self.assertEqual(self.post('/api/claim',{'id':c['id'],'revision':c['revision'],'owner_id':'chai'}).status_code,200)
        self.assertEqual(self.recover()['human'],2)

    def test_notes_and_stage_changes_are_not_overridden(self):
        self.receive('Revenda',ad=True);self.enable()
        c=self.contact()
        self.assertEqual(self.post('/api/messages',{'id':c['id'],'body':'Já conversei com a cliente por telefone.'}).status_code,200)
        self.assertEqual(self.recover()['human'],1)
        with database(self.app) as db:db.execute("UPDATE contacts SET stage='Negociação' WHERE id=?",(c['id'],))
        self.assertEqual(self.recover()['human'],1);self.assertEqual(self.sent,[])

    def test_window_uses_original_customer_timestamp_not_restart_time(self):
        self.receive('Revenda',ad=True,timestamp=time.time()-24*3600-1);self.enable()
        self.assertEqual(self.recover()['expired'],1);self.drain()
        self.assertEqual(self.sent,[])

    def test_answers_sent_minutes_apart_are_used_before_sending(self):
        now=time.time()
        self.receive('Quero começar a revender',ad=True,timestamp=now-1200)
        self.receive('Cidade Ocidental',timestamp=now-600)
        self.receive('Goiás',timestamp=now-10)
        self.enable();self.assertEqual(self.recover()['prepared'],1);self.drain()
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),('Revenda','Cidade Ocidental','GO','grasi'))
        self.assertIn('Seu atendimento foi registrado',self.sent[-1]['text']['body'])
        self.assertEqual(len(self.sent),1)

    def test_label_details_and_routing_survive_recovery(self):
        self.receive('PL. Minha marca é Bela Fit, giro 500 peças por mês.',ad=True,timestamp=time.time()-600)
        self.receive('Curitiba PR');self.enable();self.recover();self.drain()
        c=self.contact()
        self.assertEqual(c['owner_id'],'admin');self.assertIn('Marca: Bela Fit',c['note']);self.assertIn('500',c['note'])
        self.assertEqual(c['stage'],'Novo contato')

    def test_optout_in_an_earlier_unprocessed_message_is_not_lost(self):
        self.receive('Oi',ad=True);self.receive('SAIR');self.receive('Obrigada');self.enable()
        self.assertEqual(self.recover()['human'],1);self.drain();self.assertEqual(self.sent,[])

    def test_disabled_automation_and_missing_credentials_do_not_prepare_sends(self):
        self.receive('Oi',ad=True)
        self.assertIn('desativado',self.recover()['blocked'])
        self.enable();self.app.config['META_ACCESS_TOKEN']=''
        self.assertIn('credenciais',self.recover()['blocked'])
        self.assertEqual(self.sent,[])

    def test_organic_manual_and_deleted_contacts_are_not_recovered(self):
        self.receive('Vim do anúncio, quero comprar')
        self.receive('Oi',ad=True);c=self.contact()
        with database(self.app) as db:db.execute('UPDATE contacts SET manual_origin=1 WHERE id=?',(c['id'],))
        self.enable();self.assertEqual(self.recover()['prepared'],0)
        with database(self.app) as db:db.execute('UPDATE contacts SET manual_origin=0,deleted_at=? WHERE id=?',(time.time(),c['id']))
        self.assertEqual(self.recover()['prepared'],0);self.assertEqual(self.sent,[])

    def test_recovery_is_admin_only_and_requires_csrf(self):
        self.assertEqual(self.app.test_client().get('/api/automation/recovery').status_code,401)
        self.assertEqual(self.client.post('/api/automation/recover',json={}).status_code,403)
        member=self.app.test_client()
        csrf=member.post('/api/login',json={'email':'chai@example.test','password':'fixture-password-123'}).json['csrf']
        self.assertEqual(member.post('/api/automation/recover',json={},headers={'X-CSRF-Token':csrf}).status_code,403)
        self.assertEqual(member.get('/api/automation/recovery').status_code,403)
        self.assertIsNone(member.get('/api/status').json['automation_recovery'])


if __name__=='__main__':unittest.main()
