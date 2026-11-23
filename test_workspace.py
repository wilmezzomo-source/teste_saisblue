"""Bounded reads, private cache invalidation, history cursors and idle writes."""
import collections
import json
import unittest
from datetime import datetime
from unittest.mock import patch

import followups
import server
import test_access_control as fixtures


class WorkspaceTest(unittest.TestCase):
    login=fixtures.AccessControlTest.login
    post=fixtures.AccessControlTest.post
    rows=fixtures.AccessControlTest.rows
    create=fixtures.AccessControlTest.create

    def setUp(self):
        fixtures.AccessControlTest.setUp(self)
        self.current=datetime(2026,11,23,10,tzinfo=followups.LOCAL).timestamp()
        self.timer=patch('followups.clock',side_effect=lambda:self.current);self.timer.start()

    def tearDown(self):
        self.timer.stop();fixtures.AccessControlTest.tearDown(self)

    def get(self,uid='willian',headers=None,**params):
        return self.clients[uid][0].get('/api/workspace',query_string=params,headers=headers or {})

    def bulk(self,count):
        with server.database(self.app) as db:
            for _ in range(count):
                self.serial+=1;i=self.serial
                db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated,owner_id,owner,lead_profile,manual_origin) VALUES(?,?,?,'Novo contato','Teste',?,?,'grasi','Grasi','Lojista',1)",
                           ('bulk-'+str(i),'Contato fictício '+str(i),str(5554000000000+i),self.current-i,self.current-i))

    def statements(self,operation):
        statements=collections.Counter();connect=server.sqlite3.connect
        def tracked(*args,**kwargs):
            db=connect(*args,**kwargs);db.set_trace_callback(lambda sql:statements.update([sql.strip().split(None,1)[0].upper()]));return db
        with patch('server.sqlite3.connect',side_effect=tracked):result=operation()
        return result,statements

    def test_paginated_cards_preserve_full_totals_and_find_contacts_outside_the_page(self):
        self.bulk(75);first=self.get();self.assertEqual(first.status_code,200,first.json)
        self.assertEqual(len(first.json['contacts']),30);self.assertEqual(first.json['stats']['total'],75)
        self.assertEqual(first.json['pages']['Novo contato']['total'],75)
        second=self.get(pages=json.dumps({'Novo contato':1})).json
        self.assertEqual(len(second['contacts']),30)
        self.assertFalse({c['id'] for c in first.json['contacts']} & {c['id'] for c in second['contacts']})
        last=self.get(pages=json.dumps({'Novo contato':2})).json;self.assertEqual(len(last['contacts']),15)
        found=self.get(q='FICTÍCIO 75').json;self.assertEqual([c['id'] for c in found['contacts']],['bulk-75'])
        self.assertEqual(found['stats']['total'],75) # Search does not change the existing dashboard definition.
        self.assertFalse(any('messages' in c or 'audit' in c or 'note' in c for c in first.json['contacts']))

    def test_unchanged_poll_is_bodyless_and_read_only_and_queries_do_not_grow_per_card(self):
        self.bulk(100);warm=self.get()
        response,sql=self.statements(lambda:self.get(headers={'If-None-Match':warm.headers['ETag']}))
        self.assertEqual(response.status_code,304);self.assertEqual(response.data,b'')
        self.assertEqual(sql['UPDATE']+sql['INSERT']+sql['DELETE'],0);self.assertLessEqual(sql['SELECT'],4)
        _,small=self.statements(lambda:self.get())
        self.bulk(400);self.get()
        response,large=self.statements(lambda:self.get())
        self.assertEqual(large['SELECT'],small['SELECT']);self.assertLess(large['SELECT'],55)
        self.assertLess(len(response.data),200000)

    def test_updates_invalidate_only_the_current_owner_and_admin(self):
        c=self.create('grasi');other=self.create('chai')
        etags={uid:self.get(uid).headers['ETag'] for uid in ('willian','grasi','chai')}
        self.post('grasi','/api/messages',{'id':c['id'],'body':'Nota privada nova'})
        for uid in ('willian','grasi'):
            response=self.get(uid,headers={'If-None-Match':etags[uid]})
            self.assertEqual(response.status_code,200);row=next(r for r in response.json['contacts'] if r['id']==c['id'])
            self.assertEqual(row['message_count'],1)
        self.assertEqual(self.get('chai',headers={'If-None-Match':etags['chai']}).status_code,304)
        self.assertEqual(self.get('grasi',owner='chai').json['stats']['total'],0)
        self.assertEqual(self.clients['grasi'][0].get('/api/contacts/'+other['id']).status_code,404)

    def test_transfer_delete_and_restore_revoke_and_restore_private_views(self):
        c=self.create('grasi');old=self.get('grasi').headers['ETag']
        result=self.post('willian','/api/update',{'id':c['id'],'revision':c['revision'],'owner_id':'chai'})
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.get('grasi',headers={'If-None-Match':old}).json['contacts'],[])
        self.assertEqual(self.clients['grasi'][0].get('/api/contacts/'+c['id']+'?access=1').status_code,404)
        self.assertEqual(len(self.get('chai').json['contacts']),1)
        revision=self.rows('willian')[0]['revision']
        self.assertEqual(self.post('willian','/api/contacts/delete',{'id':c['id'],'revision':revision}).status_code,200)
        self.assertEqual(self.get('chai').json['stats']['total'],0)
        with server.database(self.app) as db:revision=db.execute('SELECT revision FROM contacts WHERE id=?',(c['id'],)).fetchone()[0]
        self.assertEqual(self.post('willian','/api/contacts/restore',{'id':c['id'],'revision':revision}).status_code,200)
        self.assertEqual(self.get('chai').json['stats']['total'],1)

    def test_followup_version_and_clock_changes_update_dates_without_contact_edits(self):
        c=self.create('grasi')
        with server.database(self.app) as db:db.execute("UPDATE contacts SET lead_profile='Lojista' WHERE id=?",(c['id'],))
        before=self.get('grasi').headers['ETag']
        self.post('grasi','/api/followups',{'id':c['id'],'version':0,'action':'record_step','step':'D3'})
        response=self.get('grasi',headers={'If-None-Match':before});self.assertEqual(response.status_code,200)
        row=response.json['contacts'][0];self.assertEqual(row['followup']['next_key'],'D7')
        due=row['followup']['due_on'];self.assertEqual(len(self.get('grasi',date='range',**{'from':due,'to':due}).json['contacts']),1)
        self.assertEqual(self.get('grasi',date='overdue').json['contacts'],[])
        old=response.headers['ETag'];self.current+=8*86400
        later=self.get('grasi',headers={'If-None-Match':old});self.assertEqual(later.status_code,200)
        self.assertTrue(later.json['contacts'][0]['followup']['overdue'])
        self.assertEqual(self.get('grasi',view='followups',queue='late').json['pages']['list']['total'],1)

    def test_history_is_complete_in_bounded_pages_even_with_equal_timestamps(self):
        c=self.create('grasi')
        with server.database(self.app) as db:
            for i in range(180):
                db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES(?,?,?,'in',?,'meta')",('history-'+str(i),c['id'],'Mensagem '+str(i),self.current))
            for i in range(65):db.execute("INSERT INTO audit(contact_id,actor,action,details,created) VALUES(?,'Teste','Histórico','{}',?)",(c['id'],self.current))
        client=self.clients['grasi'][0]
        newest=client.get('/api/contacts/'+c['id']).json['contact'];self.assertEqual(len(newest['messages']),100)
        older=client.get('/api/contacts/'+c['id'],query_string={'before':json.dumps(newest['history_cursor'])}).json['contact']
        self.assertEqual(len(older['messages']),80);self.assertIsNone(older['history_cursor'])
        self.assertEqual(len({m['id'] for m in newest['messages']+older['messages']}),180)
        self.assertEqual(newest['latest_incoming_at'],self.current)
        self.assertEqual(len(newest['audit']),30)
        audit=client.get('/api/contacts/'+c['id'],query_string={'audit_before':newest['audit_cursor']}).json['contact']
        self.assertFalse({e['id'] for e in newest['audit']} & {e['id'] for e in audit['audit']})
        invalid={'created':self.current,'rowid':2**100}
        self.assertEqual(client.get('/api/contacts/'+c['id'],query_string={'before':json.dumps(invalid)}).status_code,400)

    def test_map_counts_full_city_and_missing_location_without_returning_all_people(self):
        self.bulk(75)
        with server.database(self.app) as db:
            db.execute("UPDATE contacts SET city_id='4309407',city='Guaporé',state='RS' WHERE id<>'bulk-75'")
        response=self.get('grasi',view='map').json
        self.assertEqual(response['map_total'],74);self.assertEqual(response['map_groups'][0]['total'],74)
        self.assertEqual(response['pending_total'],1);self.assertEqual(len(response['contacts']),1)
        scoped=self.get('chai',view='map').json;self.assertEqual(scoped['map_total'],0)
        self.assertEqual(self.get('grasi',view='contacts',city='4309407').json['pages']['list']['total'],74)

    def test_activity_counts_follow_insert_edit_move_and_delete_without_rescanning_history(self):
        first=self.create('grasi');second=self.create('chai')
        with server.database(self.app) as db:
            db.execute("INSERT INTO messages(id,contact_id,body,direction,created,channel) VALUES('activity-test',?,'Texto','in',?,'meta')",(first['id'],self.current))
        row=self.get('grasi').json['contacts'][0];self.assertEqual((row['message_count'],row['incoming_count'],row['latest_incoming_at']),(1,1,self.current))
        with server.database(self.app) as db:db.execute("UPDATE messages SET direction='note',channel='local' WHERE id='activity-test'")
        row=self.get('grasi').json['contacts'][0];self.assertEqual((row['message_count'],row['incoming_count'],row['latest_incoming_at']),(1,0,0))
        with server.database(self.app) as db:db.execute("UPDATE messages SET contact_id=? WHERE id='activity-test'",(second['id'],))
        self.assertEqual(self.get('grasi').json['contacts'][0]['message_count'],0)
        self.assertEqual(self.get('chai').json['contacts'][0]['message_count'],1)
        with server.database(self.app) as db:db.execute("DELETE FROM messages WHERE id='activity-test'")
        self.assertEqual(self.get('chai').json['contacts'][0]['message_count'],0)

    def test_forged_admin_role_is_not_trusted_on_read_only_authentication(self):
        self.create('chai');self.create('grasi')
        with server.database(self.app) as db:db.execute("UPDATE users SET role='admin' WHERE id='grasi'")
        response=self.get('grasi').json
        self.assertEqual(response['stats']['total'],1);self.assertEqual(response['contacts'][0]['owner_id'],'grasi')

    def test_production_idle_automation_does_not_take_a_writer_lock_every_second(self):
        self.app.config['TESTING']=False
        server.run_automation_once(self.app)
        result,sql=self.statements(lambda:server.run_automation_once(self.app))
        self.assertFalse(result);self.assertEqual(sql['UPDATE']+sql['INSERT']+sql['DELETE']+sql['BEGIN'],0)

    def test_disabled_automation_ignores_expired_timers_without_taking_a_writer_lock(self):
        c=self.create('grasi');self.app.config['TESTING']=False
        server.run_automation_once(self.app)
        with server.database(self.app) as db:
            db.execute('INSERT INTO qualification_progress(contact_id,next_due,label_due) VALUES(?,?,?)',(c['id'],server.now()-10,server.now()-10))
        result,sql=self.statements(lambda:server.run_automation_once(self.app))
        self.assertFalse(result);self.assertEqual(sql['UPDATE']+sql['INSERT']+sql['DELETE']+sql['BEGIN'],0)

    def test_new_release_rebuilds_derived_rules_without_changing_customer_records(self):
        c=self.create('grasi')
        with server.database(self.app) as db:db.execute("UPDATE contacts SET lead_profile='Lojista' WHERE id=?",(c['id'],))
        self.post('grasi','/api/followups',{'id':c['id'],'version':0,'action':'record_step','step':'D3'})
        previous=self.get('grasi');self.assertEqual(previous.json['contacts'][0]['followup']['next_key'],'D7')
        with server.database(self.app) as db:original=tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone())
        with patch('server.RELEASE','2026.11.23.2'),patch.dict(followups.SEQUENCES,{'Lojista':(0,1,3,8,14,30)}):
            server.create_app(dict(self.app.config))
            current=self.get('grasi',headers={'If-None-Match':previous.headers['ETag']})
            self.assertEqual(current.status_code,200)
            self.assertEqual(current.json['contacts'][0]['followup']['next_key'],'D8')
        with server.database(self.app) as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM contacts WHERE id=?',(c['id'],)).fetchone()),original)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)


if __name__=='__main__':unittest.main()
