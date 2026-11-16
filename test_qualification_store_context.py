"""Regression conversations from the reported store/profile/location mistakes."""
import time
import unittest
from unittest.mock import patch

import test_qualification as fixtures
from qualification import parse_profile,COMPLETION
from qualification_dialogue import conversation_location
from server import database


class StoreConversationTest(unittest.TestCase):
    setUp=fixtures.QualificationTest.setUp
    tearDown=fixtures.QualificationTest.tearDown
    post=fixtures.QualificationTest.post
    enable=fixtures.QualificationTest.enable
    payload=fixtures.QualificationTest.payload
    signed=fixtures.QualificationTest.signed
    receive=fixtures.QualificationTest.receive
    drain=fixtures.QualificationTest.drain
    contact=fixtures.QualificationTest.contact

    def send_at(self,at,body,**kwargs):
        with patch('qualification.time.time',return_value=at):
            self.receive(body,timestamp=at,**kwargs);self.drain()

    def test_store_answers_are_understood_without_requiring_the_word_lojista(self):
        for body in ('loja','LOJA','Para loja','Pra minha loja','Para a minha loja',
                     'Para loja que estou abrindo','Estou abrindo uma loja','Vou abrir uma loja',
                     'Estou montando minha loja','Quero abrir uma loja online','Minha loja','Loja física',
                     'Estou abrindo uma loja para revender','Vou abrir uma loja e quero começar a revender'):
            with self.subTest(body=body):self.assertEqual(parse_profile(body),'Lojista')

    def test_store_negations_questions_and_explicit_personal_use_are_preserved(self):
        for body in ('Não tenho loja','Não estou abrindo loja','Não quero mais comprar para loja','Não quero essas peças para loja','Vocês têm loja?','Qual é o endereço da loja?'):
            self.assertIsNone(parse_profile(body),body)
        self.assertEqual(parse_profile('Não tenho loja, quero começar a revender'),'Revenda')
        self.assertEqual(parse_profile('Estou abrindo uma loja, mas as peças são para meu uso'),'Consumidor Final')
        self.assertEqual(parse_profile('Tenho uma loja, mas esta compra é para mim'),'Consumidor Final')
        self.assertIsNone(parse_profile('Quero comprar para minha loja e para meu uso'))

    def test_purchase_preposition_does_not_invent_para_or_replace_a_known_state(self):
        for body in ('Para loja','Para loja que estou abrindo','Para meu uso','Para mim','Para revender'):
            self.assertEqual(conversation_location(body),('','',None),body)
            self.assertEqual(conversation_location(body,'','SC'),('','SC',None),body)
            self.assertEqual(conversation_location(body,'belem',''),('belem','',None),body)

    def test_real_para_state_and_city_names_are_still_recognized(self):
        self.assertEqual(conversation_location('Pará')[:2],('','PA'))
        self.assertEqual(conversation_location('Sou do Pará')[:2],('','PA'))
        self.assertEqual(conversation_location('Sou do Pará e quero começar a revender')[:2],('','PA'))
        self.assertEqual(conversation_location('Belém PA e quero revender','belem','')[:2],('belem','PA'))
        for body,city,uf in (('Pará de Minas MG','Pará de Minas','MG'),('Santa Maria do Pará','Santa Maria do Pará','PA'),('Paraí RS','Paraí','RS')):
            place=conversation_location(body)[2]
            self.assertIsNotNone(place,body);self.assertEqual((place['name'],place['state']),(city,uf))

    def test_screenshot_opening_store_then_gaspar_completes_and_stops_reminders(self):
        self.enable();anchor=time.time()+1
        self.send_at(anchor,'Olá, posso ter mais informações?',ad=True)
        self.send_at(anchor+60,'Estou abrindo uma loja')
        c=self.contact();self.assertEqual((c['lead_profile'],c['qualification_state']),('Lojista','waiting_city'))
        self.assertIn('cidade',self.sent[-1]['text']['body']);self.assertNotIn('Pará',self.sent[-1]['text']['body'])
        self.send_at(anchor+120,'Gaspar SC')
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id'],c['stage']),('Lojista','Gaspar','SC','chai','Novo contato'))
        self.assertEqual(self.sent[-1]['text']['body'],COMPLETION)
        count=len(self.sent)
        for at in (anchor+20*60,anchor+3*3600,anchor+8*3600):
            with patch('qualification.time.time',return_value=at):self.drain()
        self.assertEqual(len(self.sent),count)

    def test_screenshot_city_received_first_is_not_asked_again_hours_later(self):
        self.enable();anchor=time.time()+1
        self.send_at(anchor,'Gaspar SC',ad=True)
        self.assertEqual((self.contact()['city'],self.contact()['state']),('Gaspar','SC'))
        self.send_at(anchor+89*60,'Para loja')
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),('Lojista','Gaspar','SC','chai'))
        self.assertEqual(self.sent[-1]['text']['body'],COMPLETION)
        count=len(self.sent)
        self.send_at(anchor+90*60,'Estou abrindo')
        self.send_at(anchor+91*60,'LOJA')
        self.assertEqual(len(self.sent),count)

    def test_long_store_phrase_never_saves_para_and_only_missing_city_is_requested(self):
        self.enable();self.receive('Para loja que estou abrindo',ad=True);self.drain()
        c=self.contact()
        self.assertEqual(c['lead_profile'],'Lojista')
        with database(self.app) as db:
            self.assertEqual(db.execute('SELECT state_text FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone()[0],'')
        self.receive('Sou de Santa Catarina');self.drain()
        self.assertIn('cidade',self.sent[-1]['text']['body']);self.assertIn('Santa Catarina',self.sent[-1]['text']['body'])
        self.receive('Gaspar');self.drain()
        c=self.contact();self.assertEqual((c['city'],c['state'],c['owner_id']),('Gaspar','SC','chai'))
        self.assertEqual(self.sent[-1]['text']['body'],COMPLETION)

    def test_unrecognized_store_answer_in_received_history_can_be_used_on_next_customer_message(self):
        anchor=time.time()+1
        self.send_at(anchor,'Estou abrindo uma loja',ad=True)  # Automation not active yet.
        self.enable()
        self.send_at(anchor+30*60,'Gaspar SC')
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),('Lojista','Gaspar','SC','chai'))
        self.assertEqual(len(self.sent),1);self.assertEqual(self.sent[0]['text']['body'],COMPLETION)

    def test_latest_explicit_profile_and_denial_take_precedence_over_older_store_answer(self):
        anchor=time.time()+1
        self.send_at(anchor,'Para loja',ad=True);self.enable()
        self.send_at(anchor+600,'Não tenho loja')
        self.assertEqual(self.contact()['lead_profile'],'')
        self.send_at(anchor+700,'Para meu uso')
        self.assertEqual(self.contact()['lead_profile'],'Consumidor Final')
        self.send_at(anchor+800,'Gaspar SC')
        self.assertEqual(self.contact()['owner_id'],'grasi')

    def test_matching_state_confirmation_does_not_replace_the_city(self):
        city,state,place=conversation_location('Cidade Ocidental')
        city,state,place=conversation_location('Goiás',city,state)
        self.assertEqual((place['name'],state),('Cidade Ocidental','GO'))

    def test_screenshot_personal_use_then_claudio_hours_later_keeps_consumer_profile(self):
        self.enable();anchor=time.time()+1
        self.send_at(anchor,'Olá, posso ter mais informações?',ad=True)
        self.send_at(anchor+60,'Prô meu uso')
        self.assertEqual(self.contact()['lead_profile'],'Consumidor Final')
        self.assertIn('cidade',self.sent[-1]['text']['body'])
        self.send_at(anchor+4*3600+42*60,'Cláudio Minas Gerais')
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),('Consumidor Final','Cláudio','MG','grasi'))
        self.assertEqual(self.sent[-1]['text']['body'],COMPLETION)
        count=len(self.sent)
        self.send_at(anchor+4*3600+43*60,'A partir de qtas peças pra sair no valor de atacado')
        self.assertEqual(self.contact()['lead_profile'],'Consumidor Final');self.assertEqual(len(self.sent),count)
        self.assertIn('atacado',self.contact()['messages'][-1]['body'])

    def test_personal_use_in_received_history_is_not_forgotten_after_hours_without_automation(self):
        anchor=time.time()+1
        self.send_at(anchor,'Olá',ad=True)
        self.send_at(anchor+60,'Prô meu uso')
        self.enable();self.drain();self.assertEqual(self.sent,[])
        self.send_at(anchor+5*3600,'Cláudio Minas Gerais')
        c=self.contact()
        self.assertEqual((c['lead_profile'],c['city'],c['state'],c['owner_id']),('Consumidor Final','Cláudio','MG','grasi'))
        self.assertEqual(len(self.sent),1);self.assertEqual(self.sent[0]['text']['body'],COMPLETION)

    def test_store_classification_does_not_admit_organic_contacts(self):
        self.enable();self.receive('Estou abrindo uma loja em Gaspar SC');self.drain()
        self.assertEqual(self.client.get('/api/contacts').json['contacts'],[])
        self.assertEqual(self.sent,[])


if __name__=='__main__':unittest.main()
