"""Conversation scenarios, optional brand data and conservative automatic closure."""
import json
import time
import unittest
from unittest.mock import patch

import test_qualification as fixtures
from qualification import COMPLETION, REMINDER_OFFSETS, FINAL_REMINDER_AFTER, WINDOW, LABEL_WAIT, LABEL_PROFILE
from qualification_dialogue import conversation_location, label_details
from server import database, create_app, run_automation_once


class ContextualQualificationTest(unittest.TestCase):
    setUp=fixtures.QualificationTest.setUp
    tearDown=fixtures.QualificationTest.tearDown
    post=fixtures.QualificationTest.post
    enable=fixtures.QualificationTest.enable
    payload=fixtures.QualificationTest.payload
    signed=fixtures.QualificationTest.signed
    receive=fixtures.QualificationTest.receive
    drain=fixtures.QualificationTest.drain
    contact=fixtures.QualificationTest.contact

    def row(self, number='5554999991111'):
        with database(self.app) as db:return db.execute('SELECT * FROM contacts WHERE phone=?',(number,)).fetchone()

    def progress(self, number='5554999991111'):
        with database(self.app) as db:return db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(self.row(number)['id'],)).fetchone()

    def text(self):return self.sent[-1]['text']['body']

    def tick(self, at):
        with patch('qualification.time.time',return_value=at):self.drain()

    def exhausted(self):
        self.enable();anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):
            self.receive('Bom dia',ad=True,timestamp=anchor);self.drain()
        for offset in (*REMINDER_OFFSETS,FINAL_REMINDER_AFTER):self.tick(anchor+offset)
        self.assertEqual(len(self.sent),5)
        return anchor

    def test_natural_profile_intent_and_location_inside_a_sentence(self):
        self.enable()
        for i,(body,profile,city,state,owner) in enumerate((
            ('Bom dia! As peças são para meu uso, moro em Guaporé RS.','Consumidor Final','Guaporé','RS','grasi'),
            ('Quero começar a revender, sou de Cidade Ocidental Goiás.','Revenda','Cidade Ocidental','GO','grasi'),
            ('Sou lojista, minha cidade é Florianópolis SC.','Lojista','Florianópolis','SC','chai'),
        )):
            number='555499999'+str(2000+i)
            self.receive(body,ad=True,number=number);self.drain()
            c=self.row(number)
            self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),(profile,city,state,owner))
            self.assertEqual(c['stage'],'Novo contato')
            self.assertEqual(self.text(),COMPLETION)

    def test_declining_private_label_does_not_steal_personal_use_routing(self):
        from qualification import parse_profile
        for body in ('Não tenho interesse em PL, é para meu uso','Não quero White Label, é para mim'):
            self.assertEqual(parse_profile(body),'Consumidor Final')
        self.assertEqual(parse_profile('Não quero revender, mas quero Private Label'),LABEL_PROFILE)

    def test_split_profile_answers_and_real_questions_do_not_repeat_the_menu(self):
        self.enable();self.receive('Bom dia, tudo bem?',ad=True);self.drain()
        self.assertIn('Bom dia!',self.text())
        self.assertNotIn('1 —',self.text())
        self.receive('para meu');self.drain();self.receive('uso');self.drain()
        self.assertEqual(self.row()['lead_profile'],'Consumidor Final')
        self.assertIn('seu uso',self.text())
        self.receive('Qual é o preço?');self.drain()
        self.assertIn('consultora',self.text());self.assertIn('cidade',self.text())
        self.assertNotIn('R$',self.text())
        count=len(self.sent)
        self.receive('Qual é o preço?');self.drain()
        self.assertEqual(len(self.sent),count)
        self.receive('Moro em Curitiba PR, queria saber do catálogo');self.drain()
        self.assertEqual((self.row()['city'],self.row()['state']),('Curitiba','PR'))
        self.assertEqual(self.text(),COMPLETION)

    def test_explicit_inconsistent_state_is_not_removed_by_sentence_parsing(self):
        city,state,match=conversation_location('Sou de Guaporé SC e quero revender')
        self.assertEqual((city,state),('guapore','SC'));self.assertIsNone(match)

    def test_every_label_alias_asks_details_then_routes_to_original_admin(self):
        self.enable()
        for i,term in enumerate(('White Label','Private Label','PL','WL')):
            number='555499999'+str(3000+i)
            self.receive('Olá, quero saber sobre '+term,ad=True,number=number);self.drain()
            self.assertEqual(self.row(number)['lead_profile'],LABEL_PROFILE)
            self.assertEqual(self.row(number)['owner_id'],'')
            self.receive('Guaporé RS',number=number);self.drain()
            self.assertEqual(self.row(number)['qualification_state'],'waiting_label')
            self.assertIn('marca',self.text());self.assertIn('mês',self.text())
            self.assertEqual(self.row(number)['owner_id'],'')
            self.receive('Minha marca é Bela Fit, giro 300 a 500 peças por mês',number=number);self.drain()
            c=self.row(number)
            self.assertEqual((c['owner_id'],c['qualification_state'],c['stage']),('admin','completed','Novo contato'))
            self.assertIn('Marca: Bela Fit',c['note']);self.assertIn('300 a 500',c['note'])
            self.assertEqual(self.text(),COMPLETION)
            self.assertNotIn('Willian',self.text())

    def test_label_brand_and_volume_can_arrive_before_city_and_are_not_asked_again(self):
        self.enable()
        self.receive('Quero PL. Minha marca é Urban.Fit, giro 500 peças por mês. Sou de Curitiba PR.',ad=True);self.drain()
        c=self.row()
        self.assertEqual((c['owner_id'],c['city'],c['qualification_state']),('admin','Curitiba','completed'))
        self.assertIn('Urban.Fit',c['note']);self.assertIn('500',c['note'])
        self.assertEqual(len(self.sent),1);self.assertEqual(self.text(),COMPLETION)

    def test_direct_brand_reply_with_profile_words_is_not_reclassified(self):
        self.enable();self.receive('WL, sou de Curitiba PR',ad=True);self.drain()
        self.receive('Revenda Fit');self.drain()
        self.assertEqual(self.row()['lead_profile'],LABEL_PROFILE)
        self.assertIn('volume',self.text())
        self.receive('600');self.drain()
        self.assertEqual(self.row()['owner_id'],'admin')
        self.assertIn('Marca: Revenda Fit',self.row()['note'])
        self.assertIn('600',self.row()['note'])

    def test_optional_brand_data_can_be_declined_or_left_unanswered(self):
        self.enable();self.receive('Private Label, sou de Curitiba PR',ad=True);self.drain()
        self.receive('Ainda não tenho essas informações');self.drain()
        self.assertEqual(self.row()['owner_id'],'admin')
        self.assertIn('Marca: Não informada',self.row()['note']);self.assertIn('Volume mensal: Não informado',self.row()['note'])
        number='5554999994444'
        self.receive('PL, sou de Guaporé RS',ad=True,number=number);self.drain()
        due=self.progress(number)['label_due']
        self.assertGreater(due,0)
        self.tick(due-1);self.assertEqual(self.row(number)['owner_id'],'')
        self.tick(due+1)
        self.assertEqual(self.row(number)['owner_id'],'admin')
        self.assertEqual(self.text(),COMPLETION)
        self.assertIn('Não informado',self.row(number)['note'])

    def test_optional_data_timeout_after_downtime_assigns_without_sending_outside_window(self):
        self.enable();anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):
            self.receive('PL, sou de Curitiba PR',ad=True,timestamp=anchor);self.drain()
        count=len(self.sent)
        self.tick(anchor+WINDOW+100)
        self.assertEqual((self.row()['owner_id'],self.row()['qualification_state']),('admin','completed'))
        self.assertEqual(len(self.sent),count)

    def test_expired_unsent_optional_question_does_not_abandon_label_lead(self):
        self.enable();anchor=time.time()+1
        with patch('qualification.time.time',return_value=anchor):self.receive('PL, sou de Curitiba PR',ad=True,timestamp=anchor)
        self.assertEqual(self.row()['qualification_state'],'waiting_label')
        self.tick(anchor+WINDOW+100)
        self.assertEqual(self.row()['owner_id'],'admin')
        self.assertEqual(self.sent,[])

    def test_client_request_for_consultant_skips_optional_details_after_question(self):
        self.enable();self.receive('WL, sou de Curitiba PR',ad=True);self.drain()
        self.receive('Quero falar com uma consultora');self.drain()
        self.assertEqual((self.row()['owner_id'],self.row()['qualification_state']),('admin','completed'))
        self.assertEqual(self.text(),COMPLETION)

    def test_label_routing_uses_original_admin_not_a_matching_display_name(self):
        from server import password
        self.enable()
        with database(self.app) as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',('impostor','impostor@example.test','Willian',password('fixture-password-123'),'member',0))
        self.receive('Quero WL, minha marca é Bela Fit, giro 400 peças por mês. Sou de Curitiba PR.',ad=True);self.drain()
        self.assertEqual(self.row()['owner_id'],'admin')
        outsider=self.app.test_client();outsider.post('/api/login',json={'email':'impostor@example.test','password':'fixture-password-123'})
        self.assertEqual(outsider.get('/api/contacts').json['contacts'],[])

    def test_optional_label_timer_does_not_override_manual_claim_or_optout(self):
        self.enable();self.receive('PL, sou de Guaporé RS',ad=True);self.drain()
        c=self.row();due=self.progress()['label_due']
        self.assertEqual(self.post('/api/claim',{'id':c['id'],'revision':c['revision'],'owner_id':'chai'}).status_code,200)
        count=len(self.sent);self.tick(due+1)
        self.assertEqual((self.row()['owner_id'],self.row()['qualification_state']),('chai','human'))
        self.assertEqual(len(self.sent),count)
        number='5554999994444';self.receive('WL, sou de Curitiba PR',ad=True,number=number);self.drain()
        self.receive('SAIR',number=number);self.drain()
        self.tick(time.time()+LABEL_WAIT+30)
        self.assertEqual(self.row(number)['qualification_state'],'human')
        self.assertEqual(self.row(number)['owner_id'],'')

    def test_manual_profile_edit_pauses_label_question_and_preserves_override(self):
        self.enable();self.receive('PL, sou de Guaporé RS',ad=True);self.drain()
        c=self.row();due=self.progress()['label_due']
        result=self.post('/api/update',{'id':c['id'],'revision':c['revision'],'lead_profile':'Revenda'})
        self.assertEqual(result.status_code,200,result.json)
        count=len(self.sent);self.tick(due+1)
        self.assertEqual((self.row()['lead_profile'],self.row()['qualification_state'],self.row()['owner_id']),('Revenda','human',''))
        self.assertEqual(len(self.sent),count)

    def test_label_notes_preserve_manual_notes_and_late_explicit_details(self):
        self.enable();self.receive('WL',ad=True);self.drain()
        with database(self.app) as db:db.execute("UPDATE contacts SET note=note||'\n\nObservação humana preservada' WHERE id=?",(self.row()['id'],))
        self.receive('Curitiba PR');self.drain();self.receive('Ainda não sei');self.drain()
        self.receive('Minha marca é Bela Fit, giro 700 peças mensais');self.drain()
        c=self.row()
        self.assertIn('Observação humana preservada',c['note']);self.assertIn('Bela Fit',c['note']);self.assertIn('700',c['note'])
        self.assertEqual(c['note'].count('Interesse: Marca própria'),1)
        self.assertEqual(self.text(),COMPLETION)

    def test_brand_word_and_nonmonthly_volume_are_not_silently_changed(self):
        data=label_details('Minha marca é Evolua, giro 100 peças por semana')
        self.assertEqual(data['brand'],'Evolua')
        self.assertIn('semana',data['volume']);self.assertNotIn('400',data['volume'])
        for body in ('Obrigada','Ok','Meu nome é Ana','Sou de Guaporé','R$ 500','PL'):
            with self.subTest(body=body):self.assertNotIn('brand',label_details(body,free_answer=True))
        self.assertNotIn('volume',label_details('Giro 500 reais',free_answer=True))

    def test_lost_only_after_full_cadence_and_24_hours_and_can_resume_on_reply(self):
        anchor=self.exhausted()
        with database(self.app) as db:db.execute("UPDATE contacts SET note='Cliente indicado pela loja' WHERE id=?",(self.row()['id'],))
        self.tick(anchor+WINDOW-1);self.assertEqual(self.row()['stage'],'Novo contato')
        self.tick(anchor+WINDOW+1)
        c=self.row();self.assertEqual((c['stage'],c['qualification_state']),('Perdido','no_response'))
        self.assertIn('Cliente indicado pela loja',c['note']);self.assertEqual(c['note'].count('Sem Resposta'),1)
        self.tick(anchor+WINDOW+2);self.assertEqual(self.row()['note'].count('Sem Resposta'),1)
        self.assertEqual(len(self.sent),5)
        with patch('qualification.time.time',return_value=anchor+WINDOW+3):
            self.receive('Para meu uso',timestamp=anchor+WINDOW+3);self.drain()
        c=self.row()
        self.assertEqual((c['stage'],c['lead_profile'],c['qualification_state']),('Novo contato','Consumidor Final','waiting_city'))
        self.assertEqual(c['note'],'Cliente indicado pela loja')

    def test_incomplete_or_failed_attempts_are_not_marked_lost(self):
        anchor=self.exhausted()
        with database(self.app) as db:db.execute("UPDATE messages SET status='failed' WHERE automation_kind='reminder' AND id=(SELECT id FROM messages WHERE automation_kind='reminder' LIMIT 1)")
        self.tick(anchor+WINDOW+1)
        self.assertEqual(self.row()['stage'],'Novo contato')
        self.assertNotIn('Sem Resposta',self.row()['note'])

    def test_manual_progress_or_assignment_prevents_lost_even_with_full_attempts(self):
        anchor=self.exhausted()
        with database(self.app) as db:db.execute("UPDATE contacts SET owner_id='grasi',owner='Grasi' WHERE id=?",(self.row()['id'],))
        self.tick(anchor+WINDOW+1)
        self.assertEqual(self.row()['stage'],'Novo contato')
        self.assertEqual(self.row()['owner_id'],'grasi')

    def test_delayed_delivery_failure_undoes_automatic_loss_without_sending(self):
        anchor=self.exhausted();self.tick(anchor+WINDOW+1)
        self.assertEqual(self.row()['stage'],'Perdido')
        with database(self.app) as db:
            message=db.execute("SELECT external_id FROM messages WHERE automation_kind='final'").fetchone()['external_id']
        status={'entry':[{'changes':[{'value':{'metadata':{'phone_number_id':'official-fixture'},'statuses':[{'id':message,'status':'failed','errors':[{'code':131000}]}]}}]}]}
        self.signed(status)
        self.assertEqual((self.row()['stage'],self.row()['qualification_state']),('Novo contato','human'))
        self.assertNotIn('Sem Resposta',self.row()['note'])
        self.assertEqual(len(self.sent),5)

    def test_manual_note_or_field_edit_prevents_automatic_loss(self):
        for action in ('note','field'):
            with self.subTest(action=action):
                if action=='field':
                    self.tearDown();self.setUp()
                anchor=self.exhausted();c=self.row()
                with patch('qualification.time.time',return_value=anchor+FINAL_REMINDER_AFTER+10):
                    self.csrf=self.client.post('/api/login',json={'email':'admin@example.test','password':'fixture-password-123'}).json['csrf']
                    if action=='note':
                        response=self.post('/api/messages',{'id':c['id'],'body':'Aguardando retorno combinado com a cliente.'})
                    else:
                        response=self.post('/api/update',{'id':c['id'],'revision':c['revision'],'note':'Acompanhar pessoalmente.'})
                    self.assertEqual(response.status_code,200,response.json)
                self.tick(anchor+WINDOW+1)
                self.assertEqual(self.row()['stage'],'Novo contato')
                self.assertNotIn('Sem Resposta',self.row()['note'])

    def test_internal_note_after_loss_prevents_automatic_reopening(self):
        anchor=self.exhausted();self.tick(anchor+WINDOW+1);c=self.row()
        with patch('qualification.time.time',return_value=anchor+WINDOW+2):
            self.csrf=self.client.post('/api/login',json={'email':'admin@example.test','password':'fixture-password-123'}).json['csrf']
            self.assertEqual(self.post('/api/messages',{'id':c['id'],'body':'Perda revisada pela equipe.'}).status_code,200)
        with patch('qualification.time.time',return_value=anchor+WINDOW+3):self.receive('Para meu uso',timestamp=anchor+WINDOW+3);self.drain()
        self.assertEqual(self.row()['stage'],'Perdido');self.assertEqual(len(self.sent),5)

    def test_manual_edit_after_automatic_loss_is_not_overridden_by_reopening(self):
        anchor=self.exhausted();self.tick(anchor+WINDOW+1)
        with database(self.app) as db:db.execute("UPDATE contacts SET note=note||'\nRevisado por Willian',revision=revision+1 WHERE id=?",(self.row()['id'],))
        with patch('qualification.time.time',return_value=anchor+WINDOW+3):self.receive('Para meu uso',timestamp=anchor+WINDOW+3);self.drain()
        self.assertEqual(self.row()['stage'],'Perdido');self.assertEqual(len(self.sent),5)


if __name__=='__main__':unittest.main()
