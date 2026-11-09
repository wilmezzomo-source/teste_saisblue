"""Deterministic WhatsApp qualification; no external AI or geocoding service."""
import hashlib
import json
import re
import time
import unicodedata

from locations import CITIES

PROFILES = ('Lojista', 'Revenda', 'Consumidor Final')
PROFILE_QUESTION = ('Olá! Sou o assistente virtual da Sais Blue. Para direcionar seu atendimento, '
                    'você é:\n1 — Lojista\n2 — Revenda\n3 — Consumidor Final\n'
                    'Responda com o número ou o perfil. Se preferir, escreva ATENDENTE.')
CITY_QUESTION = 'Qual é sua cidade e estado? Envie, por exemplo: Guaporé/RS. Se preferir, escreva ATENDENTE.'
STATE_NAMES = dict(zip(
    ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'),
    ('Acre','Alagoas','Amapá','Amazonas','Bahia','Ceará','Distrito Federal','Espírito Santo','Goiás','Maranhão','Mato Grosso','Mato Grosso do Sul','Minas Gerais','Pará','Paraíba','Paraná','Pernambuco','Piauí','Rio de Janeiro','Rio Grande do Norte','Rio Grande do Sul','Rondônia','Roraima','Santa Catarina','São Paulo','Sergipe','Tocantins')))


def normalize(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


CITY_LOOKUP = {(normalize(c['name']), c['state']): c for c in CITIES}
STATE_ALIASES = {normalize(name): uf for uf, name in STATE_NAMES.items()}
STATE_ALIASES.update({uf.lower(): uf for uf in STATE_NAMES})


def is_ad_referral(referral):
    if not isinstance(referral, dict):
        return False
    kind = referral.get('source_type', '')
    return kind in ('', 'ad') and (bool(referral.get('ctwa_clid')) or (kind == 'ad' and bool(referral.get('source_id'))))


def parse_profile(body):
    value = normalize(body)
    for prefix in ('eu sou ', 'sou '):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return {'1':'Lojista','lojista':'Lojista','tenho loja':'Lojista',
            '2':'Revenda','revenda':'Revenda','revendedor':'Revenda','revendedora':'Revenda',
            '3':'Consumidor Final','consumidor':'Consumidor Final','consumidora':'Consumidor Final',
            'consumidor final':'Consumidor Final','consumidora final':'Consumidor Final',
            'uso proprio':'Consumidor Final'}.get(value)


def parse_city(body):
    value = normalize(body)
    value = re.sub(r'^(?:sou de|moro em|minha cidade e|cidade de|cidade) ', '', value)
    value = value.replace(' estado de ', ' ').replace(' estado ', ' ').replace(' uf ', ' ')
    for state, uf in sorted(STATE_ALIASES.items(), key=lambda pair: -len(pair[0])):
        if value.endswith(' ' + state):
            name = value[:-(len(state) + 1)].strip()
            return CITY_LOOKUP.get((name, uf))
    return None


def settings(db):
    row = db.execute("SELECT value FROM crm_settings WHERE key='qualification'").fetchone()
    return json.loads(row['value']) if row else {'enabled': False, 'assignment_mode': 'regional', 'regional_owners': {'chai':'','grasi':''}}


def routing_group(profile, state):
    return 'chai' if profile in ('Lojista','Revenda') and state in ('RS','SC') else 'grasi'


def cancel_pending(db, cid):
    db.execute("UPDATE messages SET status='cancelled' WHERE contact_id=? AND automation=1 AND status='queued'", (cid,))


def handover(db, cid, audit, reason):
    cancel_pending(db, cid)
    db.execute("UPDATE contacts SET qualification_state='human',updated=?,revision=revision+1 WHERE id=?", (time.time(), cid))
    audit(db, 'Qualificação encaminhada à equipe', cid, {'motivo': reason}, actor='Assistente Sais Blue')


def enqueue(db, cid, incoming_id, body, step):
    mid = 'bot:' + hashlib.sha256(incoming_id.encode()).hexdigest()
    db.execute("INSERT OR IGNORE INTO messages(id,contact_id,body,direction,created,channel,status,author,automation,automation_step) VALUES(?,?,?,'out',?,'meta','queued','Assistente Sais Blue',1,?)", (mid, cid, body, time.time(), step))


def process_answer(db, cid, incoming_id, body, created, audit):
    config = settings(db)
    c = db.execute('SELECT * FROM contacts WHERE id=?', (cid,)).fetchone()
    if not config['enabled'] or c['deleted_at'] or not c['ad_origin'] or c['qualification_state'] in ('human', 'completed'):
        return
    if time.time() - created >= 86400 or created < c['qualification_last_at']:
        return
    value = normalize(body)
    if value in ('atendente','humano','pessoa','parar','pare','sair','cancelar') or re.search(r'\b(?:falar com|quero|preciso de) (?:um |uma |o |a )?(?:atendente|pessoa|humano|grasi|chai)\b', value):
        handover(db, cid, audit, 'Solicitação do cliente')
        return
    if c['qualification_state'] == 'not_started' and (c['owner'] != 'Sem responsável' or c['stage'] != 'Novo contato'):
        return  # Do not interrupt an existing conversation handled by the team.
    step, attempts = c['qualification_state'], 0
    profile, city = c['lead_profile'], None
    if step == 'not_started':
        step, reply = ('waiting_city', CITY_QUESTION) if profile else ('waiting_profile', PROFILE_QUESTION)
    elif step == 'waiting_profile':
        profile = parse_profile(body)
        if profile:
            step, reply = 'waiting_city', CITY_QUESTION
        else:
            profile, attempts = c['lead_profile'], c['qualification_attempts'] + 1
            reply = 'Não consegui identificar o perfil. ' + PROFILE_QUESTION
    elif step == 'waiting_city':
        city = parse_city(body)
        if city:
            step = 'completed'
            reply = f"Obrigado! Registrei seu perfil como {profile} e sua cidade como {city['name']}/{city['state']}. Nossa equipe continuará seu atendimento."
        else:
            attempts = c['qualification_attempts'] + 1
            reply = 'Não consegui confirmar cidade e UF. ' + CITY_QUESTION
    else:
        return
    if attempts >= 2:
        handover(db, cid, audit, 'Respostas não identificadas; conferir os campos pendentes')
        return
    cancel_pending(db, cid)
    db.execute('UPDATE contacts SET lead_profile=?,qualification_state=?,qualification_attempts=?,qualification_last_at=?,updated=?,revision=revision+1 WHERE id=?',
               (profile, step, attempts, created, time.time(), cid))
    if city:
        db.execute('UPDATE contacts SET city_id=?,city=?,state=? WHERE id=?', (city['id'], city['name'], city['state'], cid))
        audit(db, 'Perfil e localização qualificados', cid, {'perfil': profile, 'cidade': city['name'], 'uf': city['state']}, actor='Assistente Sais Blue')
        if config['assignment_mode'] == 'regional':
            group = routing_group(profile, city['state'])
            person = db.execute('SELECT id,name FROM users WHERE id=? AND active=1', (config.get('regional_owners', {}).get(group, ''),)).fetchone()
            if person:
                owner = person['name']
                db.execute('UPDATE contacts SET owner=?,owner_id=? WHERE id=?', (owner, person['id'], cid))
                audit(db, 'Responsável atribuído', cid, {'responsável': owner, 'perfil':profile, 'uf':city['state']}, actor='Assistente Sais Blue')
            else:
                audit(db, 'Atribuição pendente', cid, {'motivo':'Responsável do perfil indisponível; equipe deve assumir'}, actor='Assistente Sais Blue')
    enqueue(db, cid, incoming_id, reply, step)


def process_outbox(app, connect, transmit, audit):
    """Claim one send durably. Never retry an ambiguous network result."""
    with app.app_context(), connect(app) as db:
        db.execute('BEGIN IMMEDIATE')
        stale = db.execute("SELECT * FROM messages WHERE automation=1 AND status='sending' AND send_started<?", (time.time()-120,)).fetchall()
        for row in stale:
            db.execute("UPDATE messages SET status='uncertain' WHERE id=?", (row['id'],))
            handover(db, row['contact_id'], audit, 'Envio interrompido; conferir histórico antes de reenviar')
        row = db.execute("SELECT * FROM messages WHERE automation=1 AND status='queued' ORDER BY created,id LIMIT 1").fetchone()
        if not row:
            return False
        c = db.execute('SELECT * FROM contacts WHERE id=?', (row['contact_id'],)).fetchone()
        last = db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'", (c['id'],)).fetchone()[0]
        if c['deleted_at'] or not settings(db)['enabled'] or c['qualification_state'] != row['automation_step'] or not last or time.time()-last >= 86400:
            db.execute("UPDATE messages SET status='cancelled' WHERE id=?", (row['id'],))
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
        if result[0] != 'accepted':
            handover(db, c['id'], audit, 'Envio automático falhou ou ficou sem confirmação')
    return True
