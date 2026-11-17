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
        for profile,keys in (('Lojista',['D0','D1','D3','D7','D14']),('Revenda',['D0','D2','D5','D10']),('Consumidor Final',['D0','D1','D3','D7'])):
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

    def test_final_attempt_moves_store_and_reseller_to_internal_review_and_consumer_closes(self):
        for profile,last,review in (('Lojista',14,'2026-12-17'),('Revenda',10,'2027-01-01'),('Consumidor Final',7,'')):
            self.tick(0);c=self.lead(profile);self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
            self.tick(last)
            state=self.row(c['id'])['followup']
            if state['due_at']>self.current:self.current=state['due_at']+60
            response=self.save(c,complete='D'+str(last));self.assertEqual(response.status_code,200,response.json)
            state=response.json['followup'];self.assertEqual(state['queue'],'review' if review else 'closed')
            self.assertEqual(state['due_on'],review)
            if review:self.assertTrue(state['review'])

    def test_missed_attempts_do_not_create_a_burst_and_sequence_expires_without_marking_fake_contacts(self):
        c=self.lead();self.save(c,mode='awaiting',last_conversation_on='2026-11-17')
        self.tick(3);state=self.row(c['id'])['followup'];self.assertEqual(state['next_key'],'D3')
        self.assertEqual(self.save(c,complete='D1').status_code,400)
        self.save(c,complete='D3');state=self.row(c['id'])['followup']
        self.assertEqual(state['progress'],{'D3':'2026-11-20'});self.assertEqual(state['next_key'],'D7')
        self.tick(15);state=self.row(c['id'])['followup'];self.assertEqual(state['queue'],'review')
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

    def test_qualification_pending_after_24h_is_an_internal_lane_without_changing_bot_or_contact_stage(self):
        c=self.lead('')
        with database(self.app) as db:
            db.execute("UPDATE contacts SET city_id='',city='',state='',ad_origin=1,manual_origin=0,qualification_state='waiting_city',qualification_last_at=? WHERE id=?",(self.current-86401,c['id']))
        state=self.row(c['id'])['followup'];self.assertEqual(state['crm_stage'],'Qualificação pendente');self.assertEqual(state['queue'],'qualification_pending')
        with database(self.app) as db:
            row=db.execute('SELECT stage,qualification_state FROM contacts WHERE id=?',(c['id'],)).fetchone()
            self.assertEqual(tuple(row),('Novo contato','waiting_city'))
        self.assertEqual(self.row(c['id'])['messages'],[])

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
        state=self.row(c['id'])['followup'];self.assertEqual(state['next_key'],'D3')
        self.save(c,complete='D3');state=self.row(c['id'])['followup']
        self.assertTrue(next(p for p in state['plan'] if p['key']=='D1')['covered'])

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
        self.save(c,complete='D0');self.save(c,mode='blocked')
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


if __name__=='__main__':unittest.main()
