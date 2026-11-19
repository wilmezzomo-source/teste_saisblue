"""Internal CRM dates, access boundaries and zero WhatsApp side effects."""
import json
import unittest
from datetime import datetime,timedelta
from unittest.mock import patch

import followups as f
import test_access_control as fixtures
from server import database,create_app


class FollowupTest(unittest.TestCase):
    login=fixtures.AccessControlTest.login
    post=fixtures.AccessControlTest.post
    rows=fixtures.AccessControlTest.rows
    create=fixtures.AccessControlTest.create

    def setUp(self):
        fixtures.AccessControlTest.setUp(self)
        self.current=datetime(2026,11,17,10,tzinfo=f.LOCAL).timestamp()
        self.timer=patch('followups.clock',side_effect=lambda:self.current);self.timer.start()

    def tearDown(self):
        self.timer.stop();fixtures.AccessControlTest.tearDown(self)

    def row(self,cid):return next(c for c in self.rows('willian') if c['id']==cid)

    def lead(self,profile='Lojista',owner='grasi'):
        c=self.create(owner)
        with database(self.app) as db:db.execute('UPDATE contacts SET lead_profile=? WHERE id=?',(profile,c['id']))
        return self.row(c['id'])

    def save(self,c,actor='grasi',**fields):
        return self.post(actor,'/api/followups',dict(id=c['id'],version=self.row(c['id'])['followup']['version'],**fields))

    def tick(self,days):self.current=datetime(2026,11,17,10,tzinfo=f.LOCAL).timestamp()+days*86400

    def test_profile_sequences_and_d0_do_not_reset_after_checking_an_attempt(self):
        for profile,keys in (('Lojista',['D0','D1','D3','D7','D14','D30']),('Revenda',['D0','D2','D5','D10','D45']),('Consumidor Final',['D0','D1','D3','D7','D15'])):
            c=self.lead(profile)
            response=self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
            self.assertEqual(response.status_code,200,response.json)
            state=response.json['followup'];self.assertEqual([p['key'] for p in state['plan']],keys)
            self.assertEqual(state['next_key'],'D0')
            done=self.save(c,complete='D0').json['followup']
            self.assertEqual(done['anchor_on'],'2026-11-17')
            self.assertEqual(done['last_conversation_on'],'2026-11-17')
            self.assertEqual(done['progress']['D0'],'2026-11-17')
            self.assertEqual(done['next_key'],keys[1])

    def test_last_regular_attempt_schedules_final_call_then_manual_decision_for_every_profile(self):
        for profile,last,final,due in (('Lojista',14,30,'2026-12-17'),('Revenda',10,45,'2027-01-01'),('Consumidor Final',7,15,'2026-12-02')):
            self.tick(0);c=self.lead(profile);self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
            self.tick(last)
            response=self.save(c,action='record_step',step='D'+str(last));self.assertEqual(response.status_code,200,response.json)
            state=response.json['followup'];self.assertEqual(state['queue'],'active')
            self.assertEqual((state['next_key'],state['due_on']),('D'+str(final),due))
            self.assertFalse(state['review']);self.assertEqual(self.row(c['id'])['stage'],'Novo contato')
            self.tick(final+10)
            state=self.row(c['id'])['followup'];self.assertTrue(state['overdue']);self.assertEqual(state['queue'],'active')
            response=self.save(c,action='record_step',step='D'+str(final));self.assertEqual(response.status_code,200,response.json)
            state=response.json['followup'];self.assertEqual((state['queue'],state['due_at']),('decision',0))
            self.tick(200);row=self.row(c['id']);self.assertEqual(row['stage'],'Novo contato')
            self.assertEqual(row['followup']['queue'],'decision');self.assertEqual(row['messages'],[])
            result=self.post('grasi','/api/update',{'id':row['id'],'revision':row['revision'],'stage':'Perdido'})
            self.assertEqual(result.status_code,200,result.json)
            self.assertEqual(self.row(c['id'])['followup']['queue'],'closed')

    def test_legacy_review_becomes_a_final_call_without_losing_marks_or_custom_date(self):
        c=self.lead('Revenda')
        self.save(c,action='record_step',step='D10')
        self.save(c,review_on='2026-12-29')
        create_app(dict(self.app.config))
        state=self.row(c['id'])['followup']
        self.assertEqual((state['queue'],state['next_key'],state['due_on']),('active','D45','2026-12-29'))
        self.assertEqual(state['progress'],{'D10':'2026-11-17'})

    def test_missed_attempt_stays_overdue_until_a_real_attempt_is_recorded(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        self.tick(3);state=self.row(c['id'])['followup'];self.assertEqual(state['next_key'],'D0');self.assertTrue(state['overdue'])
        self.assertEqual(self.save(c,complete='D1').status_code,400)
        self.save(c,action='record_step',step='D3');state=self.row(c['id'])['followup']
        self.assertEqual(state['progress'],{'D3':'2026-11-20'});self.assertEqual(state['next_key'],'D7')
        self.tick(15);state=self.row(c['id'])['followup'];self.assertEqual(state['queue'],'active');self.assertTrue(state['overdue'])
        self.assertEqual(state['next_key'],'D7')
        self.assertEqual(state['progress'],{'D3':'2026-11-20'})

    def test_agreed_date_supersedes_sequence_and_active_negotiation_never_expires_by_age(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        response=self.save(c,mode='promised',next_on='2026-12-03')
        self.assertEqual(response.json['followup']['due_on'],'2026-12-03');self.assertEqual(response.json['followup']['plan'],[])
        self.save(c,mode='negotiation',next_on='2026-12-10',next_step='Confirmar tamanhos')
        self.tick(150);state=self.row(c['id'])['followup']
        self.assertEqual((state['queue'],state['label']),('active','Confirmar tamanhos'));self.assertTrue(state['overdue'])

    def test_customer_reply_suspends_sequence_and_requires_a_conversation_next_step(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('reply',?,'Quero saber os modelos','in',?,'meta')",(c['id'],self.current+60))
        state=self.row(c['id'])['followup'];self.assertEqual(state['queue'],'conversation');self.assertEqual(state['due_at'],0)
        self.assertEqual(self.save(c,complete='D0').status_code,400)
        self.save(c,mode='negotiation',next_on='2026-11-19',next_step='Apresentar catálogo')
        self.assertEqual(self.row(c['id'])['followup']['label'],'Apresentar catálogo')

    def test_automatic_loss_is_displayed_in_perdido_and_not_in_an_invented_lane(self):
        c=self.lead('',owner='')
        with database(self.app) as db:
            db.execute("UPDATE contacts SET stage='Perdido',qualification_state='no_response',note='Sem Resposta',ad_origin=1,manual_origin=0 WHERE id=?",(c['id'],))
            db.execute("INSERT INTO qualification_progress(contact_id,reminders_sent,closed_reason,auto_lost_at) VALUES(?,4,'no_response',?)",(c['id'],self.current))
        row=self.row(c['id']);state=row['followup']
        self.assertEqual((row['stage'],state['crm_stage'],state['queue']),('Perdido','Perdido','closed'))
        self.assertIn('Sem Resposta',state['label']);self.assertEqual(state['due_at'],0)
        for uid in ('chai','grasi'):
            self.assertFalse(any(row['id']==c['id'] for row in self.rows(uid)))
        self.assertNotIn('Qualificação pendente',self.clients['willian'][0].get('/api/contacts').json['stages'])

    def test_bought_customers_use_adjustable_cycle_and_exact_reference_bands(self):
        c=self.lead();self.save(c,mode='customer',last_purchase_on='2026-11-17')
        for elapsed,band in ((30,'No ciclo'),(31,'Atenção'),(45,'Atenção'),(46,'Risco'),(60,'Risco'),(61,'Inativo'),(90,'Inativo'),(91,'Dormente')):
            self.tick(elapsed);self.assertEqual(self.row(c['id'])['followup']['purchase_band'],band)
        self.save(c,cycle_days='90');self.tick(60)
        self.assertEqual(self.row(c['id'])['followup']['purchase_band'],'No ciclo')

    def test_permissions_csrf_and_optimistic_conflicts_preserve_other_attendants_data(self):
        c=self.lead(owner='chai');unassigned=self.lead(owner='')
        for row in (c,unassigned):self.assertEqual(self.save(row,mode='paused').status_code,404)
        response=self.save(c,actor='willian',mode='paused');self.assertEqual(response.status_code,200)
        stale=self.post('chai','/api/followups',{'id':c['id'],'version':0,'mode':'blocked'});self.assertEqual(stale.status_code,409)
        client=self.clients['chai'][0]
        self.assertEqual(client.post('/api/followups',json={'id':c['id'],'version':1,'mode':'blocked'}).status_code,403)
        self.assertFalse(any(row['id']==c['id'] for row in self.rows('grasi')))

    def test_invalid_dates_and_future_completions_are_rejected(self):
        c=self.lead()
        for fields in ({'mode':'invalid'},{'mode':'awaiting'},{'mode':'negotiation','next_on':'2026-12-01'},
                       {'mode':'promised','next_on':'2026-02-30'},{'cycle_days':0},{'last_conversation_on':'2027-01-01'}):
            self.assertEqual(self.save(c,**fields).status_code,400,fields)
        self.save(c,mode='awaiting',last_conversation_on='2026-11-17');self.save(c,complete='D0')
        self.assertEqual(self.save(c,complete='D1').status_code,400)

    def test_reminders_are_private_deduplicated_and_blocked_contacts_have_none(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        with database(self.app) as db:
            f.reminders(db,self.current);f.reminders(db,self.current+10)
            notices=db.execute("SELECT user_id,kind FROM notifications WHERE kind='followup'").fetchall()
            self.assertEqual([tuple(n) for n in notices],[('grasi','followup')])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
        self.save(c,mode='blocked')
        self.tick(1)
        with database(self.app) as db:
            f.reminders(db,self.current)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notifications WHERE kind='followup' AND read_at=0").fetchone()[0],0)
        self.assertEqual(self.row(c['id'])['followup']['due_at'],0)

    def test_weekend_and_evening_reminders_wait_for_business_hours(self):
        self.current=datetime(2026,11,20,10,tzinfo=f.LOCAL).timestamp()
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-20');self.save(c,complete='D0')
        state=self.row(c['id'])['followup'];self.assertEqual(state['due_on'],'2026-11-23')
        for d,hour in ((21,10),(23,8),(23,19)):
            with database(self.app) as db:f.reminders(db,datetime(2026,11,d,hour,tzinfo=f.LOCAL).timestamp())
        with database(self.app) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM notifications WHERE kind='followup'").fetchone()[0],0)
        self.current=datetime(2026,11,23,10,tzinfo=f.LOCAL).timestamp()
        state=self.row(c['id'])['followup'];self.assertEqual(state['next_key'],'D1')
        self.save(c,action='record_step',step='D1');state=self.row(c['id'])['followup']
        self.assertEqual(state['next_key'],'D3');self.assertEqual(state['due_on'],'2026-11-25')

    def test_schema_and_checklist_persist_after_restart_without_rewriting_existing_data(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17');self.save(c,complete='D0')
        create_app(dict(self.app.config))
        state=self.row(c['id'])['followup'];self.assertEqual(state['progress'],{'D0':'2026-11-17'})
        self.assertEqual(self.row(c['id'])['stage'],'Novo contato')

    def test_date_alone_starts_the_profile_sequence_and_internal_edits_do_not_modify_whatsapp_state(self):
        c=self.lead()
        with database(self.app) as db:
            db.execute("UPDATE contacts SET qualification_state='waiting_city',ad_origin=1 WHERE id=?",(c['id'],))
            db.execute("INSERT INTO qualification_progress(contact_id,city_text,state_text,cycle,anchor,reminders_sent,next_due) VALUES(?,'guapore','RS','existing',1,2,123)",(c['id'],))
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel,status,automation) VALUES('existing-bot',?,'Texto existente','out',1,'meta','queued',1)",(c['id'],))
            before_contact=tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone())
            before_progress=tuple(db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone())
            before_message=tuple(db.execute("SELECT * FROM messages WHERE id='existing-bot'").fetchone())
        response=self.save(c,last_conversation_on='2026-11-17')
        self.assertEqual(response.json['followup']['mode'],'awaiting')
        self.save(c,complete='D0');self.save(c,action='record_step',step='D3');self.save(c,mode='blocked')
        with database(self.app) as db:
            f.reminders(db,self.current)
            self.assertEqual(tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone()),before_contact)
            self.assertEqual(tuple(db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone()),before_progress)
            self.assertEqual(tuple(db.execute("SELECT * FROM messages WHERE id='existing-bot'").fetchone()),before_message)

    def test_received_optout_immediately_removes_internal_sequence_even_before_staff_edits_it(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('stop-message',?,'Não quero mais mensagens','in',?,'meta')",(c['id'],self.current+1))
        state=self.row(c['id'])['followup']
        self.assertEqual((state['mode'],state['queue'],state['due_at']),('blocked','blocked',0))
        self.assertEqual(self.save(c,complete='D0').status_code,400)

    def test_manual_terminal_stage_stops_reminders_and_purchase_does_not_guess_a_purchase_date(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        with database(self.app) as db:db.execute("UPDATE contacts SET stage='Ganho' WHERE id=?",(c['id'],))
        state=self.row(c['id'])['followup'];self.assertEqual(state['queue'],'customer');self.assertEqual(state['due_at'],0)
        with database(self.app) as db:db.execute("UPDATE contacts SET stage='Perdido' WHERE id=?",(c['id'],))
        self.assertEqual(self.row(c['id'])['followup']['queue'],'closed')

    def test_a_real_contact_can_be_recorded_earlier_on_the_due_day_without_a_premature_alert(self):
        self.current=datetime(2026,11,17,8,tzinfo=f.LOCAL).timestamp()
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        with database(self.app) as db:
            f.reminders(db,self.current)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM notifications WHERE kind='followup'").fetchone()[0],0)
        response=self.save(c,complete='D0');self.assertEqual(response.status_code,200,response.json)

    def test_direct_d3_checkbox_needs_no_history_and_schedules_the_next_step(self):
        c=self.lead();response=self.save(c,action='record_step',step='D3')
        self.assertEqual(response.status_code,200,response.json)
        state=response.json['followup'];self.assertEqual(state['progress'],{'D3':'2026-11-17'})
        self.assertEqual((state['next_key'],state['due_on']),('D7','2026-11-23'))
        self.assertEqual(state['last_conversation_on'],'');self.assertEqual(state['start_step'],3)
        self.assertFalse(state['overdue'])
        self.assertTrue(next(p for p in state['plan'] if p['key']=='D0')['before_start'])
        self.tick(6);response=self.save(c,action='record_step',step='D7')
        self.assertEqual((response.json['followup']['next_key'],response.json['followup']['due_on']),('D14','2026-11-30'))
        self.assertEqual(self.save(c,action='record_step',step='D1').status_code,400)
        self.assertEqual(self.row(c['id'])['messages'],[])
        response=self.save(c,restart=True)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['followup']['next_key'],'D0')
        self.assertEqual(response.json['followup']['last_conversation_on'],'')

    def test_late_d3_uses_the_actual_call_day_and_keeps_the_old_start_date(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        self.save(c,complete='D0');self.tick(8)
        response=self.save(c,action='record_step',step='D3');self.assertEqual(response.status_code,200,response.json)
        state=response.json['followup'];self.assertEqual(state['anchor_on'],'2026-11-17')
        self.assertEqual((state['next_key'],state['due_on']),('D7','2026-11-30'));self.assertFalse(state['overdue'])

    def test_same_second_customer_reply_suspends_calls_and_recording_activity_can_resume_them(self):
        c=self.lead()
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('before-plan',?,'Quero ver o catálogo','in',?,'meta')",(c['id'],self.current))
        self.save(c,action='record_step',step='D0')
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('after-plan',?,'Pode mandar','in',?,'meta')",(c['id'],self.current))
        self.assertEqual(self.row(c['id'])['followup']['queue'],'conversation')
        self.save(c,action='record_step',step='D1');self.assertEqual(self.row(c['id'])['followup']['queue'],'active')

    def test_reading_expired_qualification_does_not_write_or_invent_a_human_activity(self):
        c=self.lead('',owner='')
        with database(self.app) as db:
            db.execute("UPDATE contacts SET city_id='',city='',state='',ad_origin=1,manual_origin=0,qualification_state='waiting_profile' WHERE id=?",(c['id'],))
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('old-question',?,'Olá','in',?,'meta')",(c['id'],self.current-90000))
            db.execute("INSERT INTO qualification_progress(contact_id,reminders_sent,closed_reason) VALUES(?,4,'finished')",(c['id'],))
            original=tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone())
        state=self.row(c['id'])['followup']
        self.assertEqual((state['queue'],state['crm_stage'],state['last_conversation_on']),('unscheduled','Novo contato',''))
        with database(self.app) as db:self.assertEqual(tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone()),original)
        for uid in ('chai','grasi'):
            self.assertEqual(self.post(uid,'/api/followups',{'id':c['id'],'version':0,'action':'record_step','step':'D0'}).status_code,404)

    def test_legacy_pending_column_migrates_without_losing_human_owner_or_reminder(self):
        c=self.lead(owner='grasi');self.save(c,action='record_step',step='D3')
        with database(self.app) as db:
            db.execute("UPDATE contacts SET stage='Qualificação pendente',note='Retorno acordado com a loja' WHERE id=?",(c['id'],))
        create_app(dict(self.app.config))
        row=self.row(c['id']);self.assertEqual((row['stage'],row['owner_id'],row['note']),('Novo contato','grasi','Retorno acordado com a loja'))
        self.assertEqual(row['followup']['progress'],{'D3':'2026-11-17'})
        self.assertEqual(row['followup']['next_key'],'D7');self.assertIn(c['id'],[r['id'] for r in self.rows('grasi')])
        create_app(dict(self.app.config))
        with database(self.app) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE contact_id=? AND action='Coluna de qualificação pendente removida'",(c['id'],)).fetchone()[0],1)

    def test_previous_followup_schema_upgrades_without_losing_history_or_ignoring_a_new_reply(self):
        c=self.lead()
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('migration-before',?,'Olá','in',?,'meta')",(c['id'],self.current))
        self.save(c,action='record_step',step='D0')
        with database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('migration-after',?,'Tenho uma dúvida','in',?,'meta')",(c['id'],self.current+1))
            db.execute('ALTER TABLE followups DROP COLUMN start_step')
            db.execute('ALTER TABLE followups DROP COLUMN response_rowid')
        create_app(dict(self.app.config))
        state=self.row(c['id'])['followup']
        self.assertEqual(state['progress'],{'D0':'2026-11-17'})
        self.assertEqual(state['queue'],'conversation')


if __name__=='__main__':unittest.main()
