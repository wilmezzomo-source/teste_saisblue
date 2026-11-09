"""Access boundaries must hold at the API, including guessed contact IDs."""
import tempfile
import time
import unittest

from server import create_app, database, password


class AccessControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.sent = []
        self.app = create_app({'TESTING':True,'DATABASE':self.temp.name+'/crm.db','APP_URL':'',
                               'META_APP_SECRET':'fixture-secret','META_PHONE_NUMBER_ID':'fixture-phone',
                               'META_ACCESS_TOKEN':'fixture-token','SECURE_COOKIE':False})
        with database(self.app) as db:
            hashed = password('fixture-password-123')
            for i,(uid,name,role) in enumerate((('willian','Willian','admin'),('grasi','Grasi','member'),('chai','Chai','member'))):
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',(uid,uid+'@example.test',name,hashed,role,time.time()+i))
        self.clients = {}
        for uid in ('willian','grasi','chai'):
            self.login(uid)
        self.serial = 0

    def tearDown(self):
        self.temp.cleanup()

    def login(self, uid):
        c = self.app.test_client()
        response = c.post('/api/login',json={'email':uid+'@example.test','password':'fixture-password-123'})
        self.assertEqual(response.status_code,200)
        self.clients[uid] = (c,response.json['csrf'])
        return response.json

    def post(self, uid, path, fields):
        client,csrf = self.clients[uid]
        return client.post(path,json=fields,headers={'X-CSRF-Token':csrf})

    def rows(self, uid):
        return self.clients[uid][0].get('/api/contacts').json['contacts']

    def create(self, owner, actor='willian'):
        self.serial += 1
        result = self.post(actor,'/api/contacts',{'name':'Oportunidade '+str(self.serial),'phone':'55549999'+str(1000+self.serial),
                                               'city_id':'4309407','owner_id':owner})
        self.assertEqual(result.status_code,201,result.json)
        return next(c for c in self.rows('willian') if c['id']==result.json['id'])

    def test_each_attendant_sees_only_own_data_and_admin_sees_unassigned(self):
        grasi,chai,unassigned = self.create('grasi'),self.create('chai'),self.create('')
        for c in (grasi,chai,unassigned):
            self.assertEqual(self.post('willian','/api/messages',{'id':c['id'],'body':'Privado: '+c['owner']}).status_code,200)
        self.assertEqual({c['id'] for c in self.rows('willian')},{grasi['id'],chai['id'],unassigned['id']})
        self.assertEqual([c['id'] for c in self.rows('grasi')],[grasi['id']])
        self.assertEqual([c['id'] for c in self.rows('chai')],[chai['id']])
        for uid in ('grasi','chai'):
            row = self.rows(uid)[0]
            self.assertEqual(row['messages'][0]['body'],'Privado: '+row['owner'])
            self.assertEqual(self.clients[uid][0].get('/api/team').json['users'][0]['id'],uid)
            self.assertEqual(len(self.clients[uid][0].get('/api/team').json['users']),1)
            self.assertTrue(self.clients[uid][0].get('/api/status').json['own_opportunities_only'])
        self.assertFalse(self.clients['willian'][0].get('/api/status').json['own_opportunities_only'])

    def test_guessed_ids_cannot_edit_claim_annotate_or_message_foreign_cards(self):
        foreign,unassigned = self.create('chai'),self.create('')
        for c in (foreign,unassigned):
            for path,fields in (
                ('/api/update',{'revision':c['revision'],'note':'Ataque','owner_id':'grasi'}),
                ('/api/claim',{'revision':c['revision'],'owner_id':'grasi'}),
                ('/api/messages',{'body':'Nota indevida'}),
                ('/api/send',{'body':'Envio indevido','request_id':'a'*32})):
                with self.subTest(path=path,owner=c['owner']):
                    self.assertEqual(self.post('grasi',path,{'id':c['id'],**fields}).status_code,404)
        for c in self.rows('willian'):
            self.assertEqual(c['messages'],[])
            self.assertEqual(c['note'],'')

    def test_member_can_create_edit_own_but_cannot_transfer_unassign_or_elevate(self):
        c = self.create('grasi',actor='grasi')
        self.assertEqual(c['owner_id'],'grasi')
        self.assertEqual(c['qualification_state'],'human')
        for uid in ('chai',''):
            self.assertEqual(self.post('grasi','/api/update',{'id':c['id'],'revision':c['revision'],'owner_id':uid}).status_code,403)
            self.assertEqual(self.post('grasi','/api/claim',{'id':c['id'],'revision':c['revision'],'owner_id':uid}).status_code,403)
            self.assertEqual(self.post('grasi','/api/contacts',{'name':'Tentativa','phone':'5554999999999','city_id':'4309407','owner_id':uid}).status_code,403)
        self.assertEqual(self.post('grasi','/api/update',{'id':c['id'],'revision':c['revision'],'note':'Meu acompanhamento','value':120}).status_code,200)
        self.assertEqual(self.post('grasi','/api/messages',{'id':c['id'],'body':'Minha nota'}).status_code,200)
        self.assertEqual(self.post('grasi','/api/invites',{'email':'x@example.test','role':'admin'}).status_code,403)
        self.assertEqual(self.post('willian','/api/invites',{'email':'x@example.test','role':'admin'}).status_code,400)
        self.assertEqual(self.post('grasi','/api/team/update',{'id':'grasi','role':'admin','active':True}).status_code,403)
        self.assertEqual(self.post('grasi','/api/simulate',{'name':'Outro','phone':'5554999998888','body':'Oi'}).status_code,403)
        # Missing owner defaults to the logged-in member; it cannot create an unassigned card.
        result = self.post('grasi','/api/contacts',{'name':'Outra minha','phone':'5554999997777','city_id':'4309407'})
        self.assertEqual(result.status_code,201)
        self.assertEqual(len(self.rows('grasi')),2)

    def test_transfer_revokes_access_immediately_and_account_name_does_not_grant_access(self):
        c = self.create('grasi')
        with database(self.app) as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',('impostor','impostor@example.test','Grasi',password('fixture-password-123'),'member',time.time()))
        self.login('impostor')
        self.assertEqual(self.rows('impostor'),[])
        result = self.post('willian','/api/update',{'id':c['id'],'revision':c['revision'],'owner_id':'chai'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.rows('grasi'),[])
        self.assertEqual([row['id'] for row in self.rows('chai')],[c['id']])
        self.assertEqual(self.post('grasi','/api/messages',{'id':c['id'],'body':'Sem acesso'}).status_code,404)
        self.assertEqual(self.post('willian','/api/update',{'id':c['id'],'revision':1,'owner':'Grasi'}).status_code,400)

    def test_legacy_owner_migration_preserves_assignments_without_guessing_duplicate_names(self):
        c = self.create('grasi')
        ambiguous = self.create('chai')
        with database(self.app) as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',('duplicate','duplicate@example.test','Chai',password('fixture-password-123'),'member',time.time()))
            db.execute('ALTER TABLE contacts DROP COLUMN owner_id')
        create_app(dict(self.app.config))
        self.assertEqual([row['id'] for row in self.rows('grasi')],[c['id']])
        self.assertEqual(self.rows('chai'),[])
        old = next(row for row in self.rows('willian') if row['id']==ambiguous['id'])
        self.assertEqual(old['owner'],'Chai')
        self.assertEqual(old['owner_id'],'')

    def test_original_administrator_remains_the_only_global_account(self):
        self.create('')
        with database(self.app) as db:
            db.execute("UPDATE users SET role='admin' WHERE id='grasi'")
        response = self.login('grasi')
        self.assertEqual(response['user']['role'],'member')
        self.assertEqual(self.rows('grasi'),[])
        self.assertEqual(len(self.rows('willian')),1)


if __name__ == '__main__':
    unittest.main()
