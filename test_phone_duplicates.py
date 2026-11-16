from concurrent.futures import ThreadPoolExecutor
import unittest

import test_qualification as fixtures
from server import database
from phone_numbers import manual_phone,phone_identity


class PhoneDuplicateTest(unittest.TestCase):
    setUp=fixtures.QualificationTest.setUp
    tearDown=fixtures.QualificationTest.tearDown
    post=fixtures.QualificationTest.post
    payload=fixtures.QualificationTest.payload
    signed=fixtures.QualificationTest.signed
    receive=fixtures.QualificationTest.receive
    contact=fixtures.QualificationTest.contact

    def fields(self,number,**changes):
        return dict({'name':'Cliente preservada','phone':number,'city_id':'4309407','note':'Observação preservada'},**changes)

    def count(self):
        with database(self.app) as db:return db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]

    def test_format_country_code_and_mobile_ninth_digit_do_not_create_more_cards(self):
        self.assertEqual(self.post('/api/contacts',self.fields('+55 (54) 99999-2222')).status_code,201)
        for value in ('5554999992222','54 99999-2222','0055 54 99999-2222','+55 (54) 9999-2222','54 9999-2222'):
            with self.subTest(number=value):
                r=self.post('/api/contacts',self.fields(value,name='Não substituir'))
                self.assertEqual(r.status_code,409,r.json)
                self.assertIn('números duplicados',r.json['error'])
        c=self.contact();self.assertEqual(c['name'],'Cliente preservada');self.assertEqual(c['note'],'Observação preservada')
        self.assertEqual(self.count(),1)

    def test_domestic_manual_input_is_stored_with_brazil_country_code(self):
        self.assertEqual(self.post('/api/contacts',self.fields('(54) 99999-2222')).status_code,201)
        self.assertEqual(self.contact()['phone'],'5554999992222')
        self.assertEqual(self.post('/api/contacts',self.fields('+55 54 99999-2222')).status_code,409)

    def test_manual_creation_cannot_duplicate_an_ad_whatsapp_id_without_ninth_digit(self):
        self.receive('Olá pelo anúncio',ad=True,number='555499992222')
        r=self.post('/api/contacts',self.fields('+55 54 99999-2222'))
        self.assertEqual(r.status_code,409,r.json)
        self.assertEqual(self.count(),1);self.assertEqual(self.contact()['manual_origin'],0)

    def test_inbound_mobile_alias_uses_existing_manual_card_without_starting_bot(self):
        self.post('/api/contacts',self.fields('54 99999-2222'))
        cid=self.contact()['id']
        self.receive('Mensagem de continuação',ad=True,number='555499992222')
        self.assertEqual(self.count(),1)
        c=self.contact();self.assertEqual(c['id'],cid);self.assertEqual(c['phone'],'5554999992222')
        self.assertEqual(c['qualification_state'],'human');self.assertEqual(len(c['messages']),1)

    def test_foreign_owner_duplicate_is_blocked_without_revealing_the_contact(self):
        self.post('/api/contacts',self.fields('5554999992222',owner_id='chai',name='Nome privado da Chai'))
        member=self.app.test_client()
        csrf=member.post('/api/login',json={'email':'grasi@example.test','password':'fixture-password-123'}).json['csrf']
        self.assertEqual(member.get('/api/contacts').json['contacts'],[])
        r=member.post('/api/contacts',json=self.fields('54 9999-2222'),headers={'X-CSRF-Token':csrf})
        self.assertEqual(r.status_code,409,r.json)
        self.assertNotIn('Chai',str(r.json));self.assertNotIn('Nome privado',str(r.json));self.assertNotIn('id',r.json)
        self.assertEqual(self.count(),1)

    def test_trashed_number_is_reserved_and_administrator_is_told_to_restore(self):
        self.post('/api/contacts',self.fields('5554999992222'));c=self.contact()
        self.assertEqual(self.post('/api/contacts/delete',{'id':c['id'],'revision':c['revision']}).status_code,200)
        r=self.post('/api/contacts',self.fields('54 9999-2222'))
        self.assertEqual(r.status_code,409,r.json);self.assertIn('lixeira',r.json['error'])
        self.assertEqual(self.count(),1)

    def test_legacy_formatted_phone_and_existing_duplicates_are_preserved(self):
        with database(self.app) as db:
            for cid,value in (('old1','+55 (54) 9999-2222'),('old2','5554999992222')):
                db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated,note) VALUES(?,?,?,'Novo contato','Manual',1,1,'Histórico preservado')",(cid,cid,value))
        self.assertEqual(self.post('/api/contacts',self.fields('54 99999-2222')).status_code,409)
        self.assertEqual(self.count(),2)
        with database(self.app) as db:self.assertEqual([r['note'] for r in db.execute('SELECT note FROM contacts')],['Histórico preservado']*2)

    def test_competing_members_and_phone_variants_create_one_opportunity(self):
        def create(item):
            user,number=item
            client=self.app.test_client()
            csrf=client.post('/api/login',json={'email':user+'@example.test','password':'fixture-password-123'}).json['csrf']
            return client.post('/api/contacts',json=self.fields(number),headers={'X-CSRF-Token':csrf}).status_code
        with ThreadPoolExecutor(max_workers=3) as pool:
            codes=list(pool.map(create,(('admin','5554999992222'),('chai','54 9999-2222'),('grasi','+55 54 99999-2222'))))
        self.assertEqual(sorted(codes),[201,409,409]);self.assertEqual(self.count(),1)

    def test_historical_domestic_number_cannot_be_registered_again_with_country_code(self):
        with database(self.app) as db:
            db.execute("INSERT INTO contacts(id,name,phone,stage,source,created,updated) VALUES('domestic','Histórico','5499992222','Novo contato','Manual',1,1)")
        r=self.post('/api/contacts',self.fields('+55 54 99999-2222'))
        self.assertEqual(r.status_code,409,r.json);self.assertEqual(self.count(),1)
        with database(self.app) as db:self.assertEqual(db.execute('SELECT phone FROM contacts').fetchone()[0],'5499992222')

    def test_international_phone_with_same_digits_as_a_brazilian_national_number_is_distinct(self):
        for number in ('+7 999 123 4567','+55 79 99123-4567'):
            self.assertEqual(self.post('/api/contacts',self.fields(number)).status_code,201)
        self.assertEqual(self.count(),2)

    def test_landlines_and_other_countries_are_not_changed_into_brazilian_mobile_aliases(self):
        numbers=('+55 54 3443-6405','+55 54 93443-6405','+7 999 123 4567','+55 79 99123-4567','+1 415 555 2671')
        for number in numbers:
            r=self.post('/api/contacts',self.fields(number))
            self.assertEqual(r.status_code,201,(number,r.json))
        self.assertEqual(self.count(),len(numbers))
        self.assertEqual(manual_phone('+7 999 123 4567'),'79991234567')
        self.assertNotEqual(phone_identity('555434436405'),phone_identity('5554934436405'))


if __name__=='__main__':unittest.main()
