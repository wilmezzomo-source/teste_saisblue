"""Durable qualification of ad leads with incremental answers and bounded follow-ups."""
import hashlib
import json
import re
import time
import unicodedata

from locations import CITIES
from notifications import notify_assigned

PROFILES = ('Lojista', 'Revenda', 'Consumidor Final')
PROFILE_QUESTION = ('Olá! Sou o assistente virtual da Sais Blue. Para direcionar seu atendimento, '
                    'você é:\n1 — Lojista\n2 — Revenda\n3 — Consumidor Final\nResponda com o número ou o perfil.')
CITY_QUESTION = 'Qual é sua cidade e estado? Você pode enviar a cidade e a UF em mensagens separadas. Exemplo: Guaporé e depois RS.'
REMINDER_DELAYS = (5*60, 10*60, 30*60, 60*60)
FINAL_REMINDER_AFTER = 23*3600+50*60
WINDOW = 24*3600
STATE_NAMES = dict(zip(
    ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'),
    ('Acre','Alagoas','Amapá','Amazonas','Bahia','Ceará','Distrito Federal','Espírito Santo','Goiás','Maranhão','Mato Grosso','Mato Grosso do Sul','Minas Gerais','Pará','Paraíba','Paraná','Pernambuco','Piauí','Rio de Janeiro','Rio Grande do Norte','Rio Grande do Sul','Rondônia','Roraima','Santa Catarina','São Paulo','Sergipe','Tocantins')))


def normalize(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


CITY_LOOKUP = {(normalize(c['name']), c['state']): c for c in CITIES}
CITY_NAMES = {name for name, uf in CITY_LOOKUP}
STATE_ALIASES = {normalize(name): uf for uf, name in STATE_NAMES.items()}
STATE_ALIASES.update({uf.lower(): uf for uf in STATE_NAMES})


def is_ad_referral(referral):
    if not isinstance(referral, dict):
        return False
    kind = referral.get('source_type', '')
    return kind in ('', 'ad') and (bool(referral.get('ctwa_clid')) or (kind == 'ad' and bool(referral.get('source_id'))))


def parse_profile(body):
    value = normalize(body)
    numbered = re.fullmatch(r'(?:opcao )?([123])', value)
    if numbered:
        return PROFILES[int(numbered[1])-1]
    aliases = {
        'Lojista': ('lojista', 'tenho loja', 'tenho uma loja', 'possuo loja', 'possuo uma loja'),
        'Revenda': ('revenda','revendedor','revendedora','quero revender','revendo'),
        'Consumidor Final': ('consumidor final','consumidora final','consumidor','consumidora','cliente final','uso proprio','para mim'),
    }
    matches = set()
    for profile, phrases in aliases.items():
        for phrase in phrases:
            for match in re.finditer(r'\b'+re.escape(phrase)+r'\b', value):
                if not {'nao','nem'}.intersection(value[:match.start()].split()[-3:]):
                    matches.add(profile)
    return next(iter(matches)) if len(matches)==1 else None


def location_text(body):
    value = normalize(body)
    value = re.sub(r'^(?:(?:eu )?sou de|(?:eu )?moro em|minha cidade e|meu municipio e|cidade de|cidade|municipio) ', '', value)
    return value.replace(' estado de ', ' ').replace(' estado ', ' ').replace(' uf ', ' ')


def parse_city(body):
    value = location_text(body)
    for state, uf in sorted(STATE_ALIASES.items(), key=lambda pair: -len(pair[0])):
        if value.endswith(' ' + state):
            name = value[:-(len(state) + 1)].strip()
            name = re.sub(r' (?:no|em|de|do)$','',name)
            city = CITY_LOOKUP.get((name,uf))
            if city:
                return city
    return None


def accumulate_location(body, pending_city='', pending_state=''):
    city = parse_city(body)
    if city:
        return normalize(city['name']), city['state'], city
    value = location_text(body)
    explicit_state = re.sub(r'^(?:meu estado e|o estado e|estado de|estado|uf|sou do|sou de|e) ', '', normalize(body))
    # Full names shared by cities and states need context or an explicit UF prefix.
    if explicit_state in STATE_ALIASES and (explicit_state not in CITY_NAMES or pending_city or explicit_state!=value):
        pending_state = STATE_ALIASES[explicit_state]
    elif value in CITY_NAMES:
        pending_city = value
    return pending_city, pending_state, CITY_LOOKUP.get((pending_city,pending_state))


def next_question(profile, pending_city='', pending_state=''):
    if not profile:
        return PROFILE_QUESTION
    if pending_city and not pending_state:
        name=next(c['name'] for c in CITIES if normalize(c['name'])==pending_city)
        return f'Anotei a cidade {name}. Qual é o estado (UF)?'
    if pending_state and not pending_city:
        return f'Anotei o estado {pending_state}. Qual é sua cidade?'
    if pending_city and pending_state:
        return 'Ainda preciso confirmar a combinação de cidade e UF. '+CITY_QUESTION
    return CITY_QUESTION


def settings(db):
    row = db.execute("SELECT value FROM crm_settings WHERE key='qualification'").fetchone()
    return json.loads(row['value']) if row else {'enabled': False, 'assignment_mode': 'regional', 'regional_owners': {'chai':'','grasi':''}}


def routing_group(profile, state):
    return 'chai' if profile=='Lojista' or (profile=='Revenda' and state in ('RS','SC')) else 'grasi'


def cancel_pending(db, cid):
    db.execute("UPDATE messages SET status='cancelled' WHERE contact_id=? AND automation=1 AND status='queued'", (cid,))
    db.execute('UPDATE qualification_progress SET next_due=0 WHERE contact_id=?',(cid,))


def handover(db, cid, audit, reason):
    cancel_pending(db, cid)
    db.execute("UPDATE qualification_progress SET closed_reason='paused' WHERE contact_id=?",(cid,))
    db.execute("UPDATE contacts SET qualification_state='human',updated=?,revision=revision+1 WHERE id=?", (time.time(), cid))
    audit(db, 'Qualificação encaminhada à equipe', cid, {'motivo': reason}, actor='Assistente Sais Blue')


def enqueue(db, cid, incoming_id, body, step, kind='question', cycle=''):
    mid = 'bot:' + hashlib.sha256(incoming_id.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO messages(id,contact_id,body,direction,created,channel,status,author,automation,automation_step,automation_kind,automation_cycle) VALUES(?,?,?,'out',?,'meta','queued','Assistente Sais Blue',1,?,?,?)", (mid, cid, body, time.time(), step,kind,cycle))


def process_answer(db, cid, incoming_id, body, created, audit):
    config = settings(db)
    c = db.execute('SELECT * FROM contacts WHERE id=?', (cid,)).fetchone()
    if not config['enabled'] or c['deleted_at'] or not c['ad_origin'] or c['qualification_state'] in ('human', 'completed'):
        return
    if time.time() - created >= WINDOW or created < c['qualification_last_at']:
        return
    value = normalize(body)
    if value in ('parar','pare','sair','cancelar','stop') or re.search(r'\bnao (?:quero|desejo) (?:mais |receber )?mensagens\b', value):
        handover(db, cid, audit, 'Cliente pediu para interromper mensagens automáticas')
        return
    if c['qualification_state'] == 'not_started' and (c['owner'] != 'Sem responsável' or c['stage'] != 'Novo contato'):
        return
    db.execute('INSERT OR IGNORE INTO qualification_progress(contact_id) VALUES(?)',(cid,))
    progress = db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(cid,)).fetchone()
    profile = parse_profile(body) or c['lead_profile']
    pending_city, pending_state, city = accumulate_location(body,progress['city_text'] or (normalize(c['city']) if c['city_id'] else ''),progress['state_text'] or (c['state'] if c['city_id'] else ''))
    step = 'completed' if profile and city else ('waiting_city' if profile else 'waiting_profile')
    reply = next_question(profile,pending_city,pending_state) if step!='completed' else f"Obrigado! Registrei seu perfil como {profile} e sua cidade como {city['name']}/{city['state']}. Continuaremos seu atendimento por aqui."
    cancel_pending(db, cid)
    db.execute('UPDATE contacts SET lead_profile=?,qualification_state=?,qualification_attempts=?,qualification_last_at=?,updated=?,revision=revision+1 WHERE id=?',
               (profile,step,0 if profile or city else c['qualification_attempts']+1,created,time.time(),cid))
    db.execute('''UPDATE qualification_progress SET city_text=?,state_text=?,cycle=?,anchor=?,reminders_sent=0,
                  next_due=0,closed_reason=? WHERE contact_id=?''',
               (pending_city,pending_state,incoming_id,created,'completed' if step=='completed' else '',cid))
    if city:
        db.execute('UPDATE contacts SET city_id=?,city=?,state=? WHERE id=?',(city['id'],city['name'],city['state'],cid))
    if step=='completed':
        audit(db, 'Perfil e localização qualificados', cid, {'perfil':profile,'cidade':city['name'],'uf':city['state']}, actor='Assistente Sais Blue')
        if config['assignment_mode']=='regional':
            group = routing_group(profile,city['state'])
            person = db.execute('SELECT id,name FROM users WHERE id=? AND active=1',(config.get('regional_owners',{}).get(group,''),)).fetchone()
            if person:
                db.execute('UPDATE contacts SET owner=?,owner_id=? WHERE id=?',(person['name'],person['id'],cid))
                notify_assigned(db,cid,c['owner_id'])
                audit(db,'Responsável atribuído',cid,{'responsável':person['name'],'perfil':profile,'uf':city['state']},actor='Assistente Sais Blue')
            else:
                audit(db,'Atribuição pendente',cid,{'motivo':'Responsável do perfil indisponível; equipe deve assumir'},actor='Assistente Sais Blue')
    enqueue(db,cid,incoming_id,reply,step,cycle=incoming_id)


def migrate_rules(db, audit):
    """Apply the revised ad routing once; preserve manual opportunities and stages."""
    config=settings(db)
    key='qualification_rules_20261109_6'
    if not config['enabled'] or db.execute('SELECT 1 FROM crm_settings WHERE key=?',(key,)).fetchone():
        return
    if config['assignment_mode']=='regional':
        chai=db.execute('SELECT id,name FROM users WHERE id=? AND active=1',(config.get('regional_owners',{}).get('chai',''),)).fetchone()
        if not chai:
            return
        for c in db.execute("SELECT * FROM contacts WHERE ad_origin=1 AND manual_origin=0 AND deleted_at=0 AND lead_profile='Lojista' AND stage NOT IN ('Ganho','Perdido') AND owner_id<>?",(chai['id'],)).fetchall():
            # Unfinished questions still wait for location before assignment.
            if c['qualification_state'] not in ('completed','human') or not c['city_id']:
                continue
            db.execute('UPDATE contacts SET owner=?,owner_id=?,updated=?,revision=revision+1 WHERE id=?',(chai['name'],chai['id'],time.time(),c['id']))
            notify_assigned(db,c['id'],c['owner_id'])
            audit(db,'Regra de Lojista aplicada',c['id'],{'responsável':chai['name'],'motivo':'Todo Lojista direcionado à Chai'},actor='Assistente Sais Blue')
    db.execute('INSERT INTO crm_settings VALUES(?,?)',(key,'done'))


def resume_legacy_questions(db, audit):
    key='qualification_resume_unrecognized_v1'
    if not settings(db)['enabled'] or db.execute('SELECT 1 FROM crm_settings WHERE key=?',(key,)).fetchone():
        return
    for c in db.execute("SELECT * FROM contacts WHERE ad_origin=1 AND manual_origin=0 AND deleted_at=0 AND stage='Novo contato' AND owner_id='' AND qualification_state='human' AND qualification_attempts>=1").fetchall():
        last=db.execute("SELECT details FROM audit WHERE contact_id=? AND action='Qualificação encaminhada à equipe' ORDER BY id DESC LIMIT 1",(c['id'],)).fetchone()
        if not last or json.loads(last['details']).get('motivo')!='Respostas não identificadas; conferir os campos pendentes':
            continue
        db.execute('UPDATE contacts SET qualification_state=?,qualification_attempts=0,updated=?,revision=revision+1 WHERE id=?',('waiting_city' if c['lead_profile'] else 'waiting_profile',time.time(),c['id']))
        db.execute('INSERT OR IGNORE INTO qualification_progress(contact_id) VALUES(?)',(c['id'],))
        name,uf='',''
        for message in reversed(db.execute("SELECT body FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' ORDER BY created DESC,id DESC LIMIT 12",(c['id'],)).fetchall()):
            name,uf,_=accumulate_location(message['body'],name,uf)
        last_in=db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'",(c['id'],)).fetchone()[0] or c['qualification_last_at']
        db.execute("UPDATE qualification_progress SET city_text=?,state_text=?,cycle=?,anchor=?,next_due=?,reminders_sent=0,closed_reason='' WHERE contact_id=?",(name,uf,'recovered:'+c['id'],last_in,min(time.time()+300,last_in+FINAL_REMINDER_AFTER),c['id']))
        audit(db,'Qualificação retomada sem limite de duas respostas',c['id'],actor='Assistente Sais Blue')
        if c['lead_profile'] and CITY_LOOKUP.get((name,uf)) and time.time()-last_in<WINDOW:
            process_answer(db,c['id'],'recovered:'+c['id'],'',last_in,audit)
    db.execute('INSERT INTO crm_settings VALUES(?,?)',(key,'done'))


def schedule_reminder(db, audit):
    """One durable timer per unanswered question; no catch-up message bursts."""
    if not settings(db)['enabled']:
        return
    current=time.time()
    db.execute('''INSERT OR IGNORE INTO qualification_progress(contact_id,cycle,anchor,next_due)
        SELECT c.id,'legacy:'||c.id,MAX(m.created),MIN(?,MAX(m.created)+?)
        FROM contacts c JOIN messages m ON m.contact_id=c.id AND m.direction='in' AND m.channel='meta'
        WHERE NOT EXISTS(SELECT 1 FROM qualification_progress p WHERE p.contact_id=c.id) AND c.ad_origin=1 AND c.manual_origin=0 AND c.deleted_at=0 AND c.qualification_state IN ('waiting_profile','waiting_city')
        GROUP BY c.id''',(current+300,FINAL_REMINDER_AFTER))
    progress=db.execute('SELECT * FROM qualification_progress WHERE next_due>0 AND next_due<=? ORDER BY next_due,contact_id LIMIT 1',(current,)).fetchone()
    if not progress:
        return
    c=db.execute('SELECT * FROM contacts WHERE id=?',(progress['contact_id'],)).fetchone()
    if c['deleted_at'] or not c['ad_origin'] or c['manual_origin'] or c['qualification_state'] not in ('waiting_profile','waiting_city'):
        db.execute("UPDATE qualification_progress SET next_due=0,closed_reason='paused' WHERE contact_id=?",(c['id'],))
        return
    last=db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'",(c['id'],)).fetchone()[0]
    if not last or current-last>=WINDOW:
        db.execute("UPDATE qualification_progress SET next_due=0,closed_reason='window_closed' WHERE contact_id=?",(c['id'],))
        audit(db,'Retomadas aguardam nova mensagem do cliente',c['id'],{'motivo':'Janela de 24 horas encerrada'},actor='Assistente Sais Blue')
        return
    final=current>=progress['anchor']+FINAL_REMINDER_AFTER or progress['reminders_sent']>=4
    index=5 if final else progress['reminders_sent']+1
    prefix='Ainda podemos continuar seu cadastro na Sais Blue? ' if final else 'Podemos continuar? '
    reply=prefix+next_question(c['lead_profile'],progress['city_text'],progress['state_text'])+' Se não quiser mais mensagens, responda SAIR.'
    enqueue(db,c['id'],f'reminder:{progress["cycle"]}:{index}',reply,c['qualification_state'],kind='final' if final else 'reminder',cycle=progress['cycle'])
    db.execute('UPDATE qualification_progress SET next_due=0 WHERE contact_id=?',(c['id'],))


def schedule_after_send(db, row):
    progress=db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(row['contact_id'],)).fetchone()
    if not progress or (row['automation_cycle'] and row['automation_cycle']!=progress['cycle']):
        return
    c=db.execute('SELECT qualification_state FROM contacts WHERE id=?',(row['contact_id'],)).fetchone()
    if c['qualification_state'] not in ('waiting_profile','waiting_city'):
        return
    count=5 if row['automation_kind']=='final' else progress['reminders_sent']+(1 if row['automation_kind']=='reminder' else 0)
    due=(time.time()+REMINDER_DELAYS[count]) if count<4 else progress['anchor']+FINAL_REMINDER_AFTER
    if count>=5:
        due=0
    db.execute('UPDATE qualification_progress SET reminders_sent=?,next_due=?,closed_reason=? WHERE contact_id=?',
               (count,due,'finished' if count>=5 else '',row['contact_id']))


def process_outbox(app, connect, transmit, audit):
    """Claim one send durably. Never retry an ambiguous network result."""
    with app.app_context(), connect(app) as db:
        db.execute('BEGIN IMMEDIATE')
        stale = db.execute("SELECT * FROM messages WHERE automation=1 AND status='sending' AND send_started<?", (time.time()-120,)).fetchall()
        for row in stale:
            db.execute("UPDATE messages SET status='uncertain' WHERE id=?", (row['id'],))
            if not row['automation_cycle'] or db.execute('SELECT 1 FROM qualification_progress WHERE contact_id=? AND cycle=?',(row['contact_id'],row['automation_cycle'])).fetchone():
                handover(db, row['contact_id'], audit, 'Envio interrompido; conferir histórico antes de reenviar')
        resume_legacy_questions(db,audit)
        migrate_rules(db,audit)
        schedule_reminder(db,audit)
        row = db.execute("SELECT * FROM messages WHERE automation=1 AND status='queued' ORDER BY created,id LIMIT 1").fetchone()
        if not row:
            return False
        c = db.execute('SELECT * FROM contacts WHERE id=?', (row['contact_id'],)).fetchone()
        last = db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'", (c['id'],)).fetchone()[0]
        current_cycle = not row['automation_cycle'] or db.execute('SELECT 1 FROM qualification_progress WHERE contact_id=? AND cycle=?',(c['id'],row['automation_cycle'])).fetchone()
        if c['deleted_at'] or not settings(db)['enabled'] or c['qualification_state'] != row['automation_step'] or not last or time.time()-last >= WINDOW or not current_cycle:
            db.execute("UPDATE messages SET status='cancelled' WHERE id=?", (row['id'],))
            if last and time.time()-last>=WINDOW and current_cycle:
                db.execute("UPDATE qualification_progress SET next_due=0,closed_reason='window_closed' WHERE contact_id=?",(c['id'],))
            return True
        if not app.config['META_ACCESS_TOKEN'] or not app.config['META_PHONE_NUMBER_ID']:
            db.execute("UPDATE messages SET status='failed' WHERE id=?", (row['id'],))
            handover(db, c['id'], audit, 'Credenciais de envio indisponíveis')
            return True
        db.execute("UPDATE messages SET status='sending',send_started=? WHERE id=? AND status='queued'", (time.time(), row['id']))
    result = transmit(app, c['phone'], row['body'])
    with app.app_context(), connect(app) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE messages SET status=?,external_id=?,error_code=?,error_detail=? WHERE id=?', (*result, row['id']))
        db.execute('UPDATE contacts SET updated=? WHERE id=?', (time.time(), c['id']))
        if result[0]=='accepted':
            schedule_after_send(db,row)
        elif not row['automation_cycle'] or db.execute('SELECT 1 FROM qualification_progress WHERE contact_id=? AND cycle=?',(c['id'],row['automation_cycle'])).fetchone():
            handover(db, c['id'], audit, 'Envio automático falhou ou ficou sem confirmação')
    return True
