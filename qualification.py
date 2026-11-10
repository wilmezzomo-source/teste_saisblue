"""Durable qualification of ad leads with incremental answers and bounded follow-ups."""
import hashlib
import json
import re
import time

from qualification_location import (normalize, parse_city, accumulate_location, display_city,
                                    CITY_LOOKUP, CITY_NAMES, STATE_NAMES, STATE_ALIASES)
from notifications import notify_assigned

PROFILES = ('Lojista', 'Revenda', 'Consumidor Final')
WELCOME = 'Oi! Sou o assistente virtual da Sais Blue. '
REMINDER_OFFSETS = (20*60, 3*3600, 8*3600)
MIN_REMINDER_GAP = 60*60
FINAL_REMINDER_AFTER = 23*3600+50*60
WINDOW = 24*3600

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
        'Revenda': ('revenda','revendedor','revendedora','quero revender','revendo','revender'),
        'Consumidor Final': ('consumidor final','consumidora final','consumidor','consumidora','cliente final','uso proprio','para mim'),
    }
    matches = set()
    for profile, phrases in aliases.items():
        for phrase in phrases:
            for match in re.finditer(r'\b'+re.escape(phrase)+r'\b', value):
                if not {'nao','nem'}.intersection(value[:match.start()].split()[-3:]):
                    matches.add(profile)
    return next(iter(matches)) if len(matches)==1 else None


def next_question(profile, pending_city='', pending_state='', variant=0):
    if not profile:
        return (
            'Você compra para sua loja, para revender ou para uso próprio?\n1 — Lojista\n2 — Revenda\n3 — Consumidor Final',
            'Para eu te direcionar: você tem loja, trabalha com revenda ou procura peças para você?',
            'A compra é para loja, revenda ou uso próprio?',
        )[variant%3]
    name=display_city(pending_city)
    if pending_city and not pending_state:
        return (f'Encontrei mais de uma cidade chamada {name}. Qual é o estado?',
                f'Só falta a UF de {name} para eu te direcionar.',
                f'{name} fica em qual estado?')[variant%3]
    if pending_state and not pending_city:
        return (f'Qual é sua cidade em {STATE_NAMES[pending_state]}?',
                f'Só preciso do nome da cidade em {STATE_NAMES[pending_state]} para continuar.')[variant%2]
    if pending_city and pending_state:
        return (f'Não encontrei {name}/{pending_state}. Pode confirmar a cidade ou o estado?',
                f'Pode conferir se a cidade é {name} e a UF é {pending_state}?')[variant%2]
    return ('De qual cidade você fala?', 'Me conta sua cidade para continuarmos?', 'Qual é o nome da sua cidade?')[variant%3]


def reminder_text(profile, pending_city, pending_state, attempt, final=False):
    if final:
        return 'Vou deixar a conversa em aberto por aqui. Quando quiser retomar, é só responder esta mensagem. Se preferir encerrar as mensagens, responda SAIR.'
    question=next_question(profile,pending_city,pending_state,attempt-1)
    if attempt==1:
        return 'Oi! '+question+' Se preferir encerrar as mensagens, responda SAIR.'
    if attempt==2:
        return 'Seu atendimento ficou salvo por aqui. '+question
    missing=('se a compra é para loja, revenda ou uso próprio' if not profile else
             'só a UF de '+display_city(pending_city) if pending_city and not pending_state else
             'a cidade e a UF corretas' if pending_city and pending_state else 'sua cidade')
    return 'Quando puder, me envie '+missing+' para continuarmos.'


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


TECHNICAL_PAUSES = {
    'Credenciais de envio indisponíveis',
    'Envio automático falhou ou ficou sem confirmação',
    'Envio interrompido; conferir histórico antes de reenviar',
    'A Meta informou falha de entrega da mensagem automática',
}


def can_resume_after_reply(db,c,created,incoming_id=""):
    if not c or c['qualification_state']!='human' or not c['ad_origin'] or c['manual_origin'] or c['deleted_at'] or c['owner_id'] or c['stage']!='Novo contato':
        return False
    pause=db.execute("SELECT created,details FROM audit WHERE contact_id=? AND action='Qualificação encaminhada à equipe' ORDER BY id DESC LIMIT 1",(c['id'],)).fetchone()
    if not pause or time.time()-created>=WINDOW:
        return False
    progress=db.execute('SELECT cycle FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone()
    cycle=progress['cycle'].removesuffix(':cadence2') if progress else ''
    cycle=cycle.removeprefix('recovered-reply:')
    identifiable=cycle and not cycle.startswith(('legacy:','recovered:','repaired:'))
    fresh=created>pause['created'] or (created>=int(pause['created']) and identifiable and incoming_id and incoming_id!=cycle)
    if not fresh:
        return False
    try:
        return json.loads(pause['details']).get('motivo') in TECHNICAL_PAUSES
    except (ValueError,TypeError):
        return False


def process_answer(db, cid, incoming_id, body, created, audit):
    config = settings(db)
    c = db.execute('SELECT * FROM contacts WHERE id=?', (cid,)).fetchone()
    if config['enabled'] and can_resume_after_reply(db,c,created,incoming_id):
        db.execute("UPDATE contacts SET qualification_state=? WHERE id=?",('waiting_city' if c['lead_profile'] else 'waiting_profile',cid))
        audit(db,'Assistente retomado após nova resposta do cliente',cid,actor='Assistente Sais Blue')
        c=db.execute('SELECT * FROM contacts WHERE id=?',(cid,)).fetchone()
    if not config['enabled'] or c['deleted_at'] or not c['ad_origin'] or c['qualification_state'] in ('human', 'completed'):
        return
    if time.time()-created>=WINDOW or created<c['qualification_last_at']-120:
        return
    created=max(created,c['qualification_last_at'])
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
    if not city and (pending_city,pending_state)==(progress['city_text'],progress['state_text']):
        fragments=[m['body'] for m in reversed(db.execute("SELECT body FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' AND created>=? ORDER BY created DESC,rowid DESC LIMIT 4",(cid,created-120)).fetchall())]
        for count in range(2,len(fragments)+1):
            joined=' '.join(fragments[-count:])
            if len(joined)>160:
                continue
            name,uf,match=accumulate_location(joined,pending_city,pending_state)
            if match or (name,uf)!=(pending_city,pending_state):
                pending_city,pending_state,city=name,uf,match
                break

    step = 'completed' if profile and city else ('waiting_city' if profile else 'waiting_profile')
    unchanged=step==c['qualification_state'] and profile==c['lead_profile'] and (pending_city,pending_state)==(progress['city_text'],progress['state_text'])
    asked=db.execute("SELECT created FROM messages WHERE contact_id=? AND automation=1 AND automation_kind='question' AND automation_step=? AND status IN ('accepted','sent','delivered','read','sending','uncertain') ORDER BY created DESC LIMIT 1",(cid,step)).fetchone()
    suppress=unchanged and asked and time.time()-asked['created']<120
    attempt=c['qualification_attempts']+1 if step==c['qualification_state'] else 0
    reply=next_question(profile,pending_city,pending_state,attempt) if step!='completed' else f"Perfeito! Anotei {city['name']}/{city['state']}. Seus dados ficaram salvos para continuarmos por aqui."
    cancel_pending(db, cid)
    db.execute('UPDATE contacts SET lead_profile=?,qualification_state=?,qualification_attempts=?,qualification_last_at=?,updated=?,revision=revision+1 WHERE id=?',
               (profile,step,attempt,created,time.time(),cid))
    db.execute('''UPDATE qualification_progress SET city_text=?,state_text=?,cycle=?,anchor=?,reminders_sent=0,
                  next_due=0,closed_reason=?,cadence_version=2 WHERE contact_id=?''',
               (pending_city,pending_state,incoming_id,created,'completed' if step=='completed' else '',cid))
    if city:
        db.execute('UPDATE contacts SET city_id=?,city=?,state=? WHERE id=?',(city['id'],city['name'],city['state'],cid))
    if step=='completed':
        audit(db, 'Perfil e localização qualificados', cid, {'perfil':profile,'cidade':city['name'],'uf':city['state']}, actor='Assistente Sais Blue')
        person=assign_qualified(db,cid,c['owner_id'],config,profile,city,audit)
        if person:
            reply=f"Perfeito! Anotei {city['name']}/{city['state']}. Sua conversa foi direcionada para {person['name']}."
    if suppress:
        due=next_reminder_due(created,0,time.time())
        db.execute('UPDATE qualification_progress SET next_due=? WHERE contact_id=?',(due,cid))
        return
    introduced=db.execute("SELECT 1 FROM messages WHERE contact_id=? AND automation=1 AND status IN ('accepted','sent','delivered','read','sending','uncertain') LIMIT 1",(cid,)).fetchone()
    if not introduced:
        reply=WELCOME+reply
    enqueue(db,cid,incoming_id,reply,step,cycle=incoming_id)



def assign_qualified(db, cid, previous_owner, config, profile, city, audit):
    if config['assignment_mode']!='regional':
        return None
    group=routing_group(profile,city['state'])
    person=db.execute('SELECT id,name FROM users WHERE id=? AND active=1',(config.get('regional_owners',{}).get(group,''),)).fetchone()
    if person:
        db.execute('UPDATE contacts SET owner=?,owner_id=? WHERE id=?',(person['name'],person['id'],cid))
        notify_assigned(db,cid,previous_owner)
        audit(db,'Responsável atribuído',cid,{'responsável':person['name'],'perfil':profile,'uf':city['state']},actor='Assistente Sais Blue')
    else:
        audit(db,'Atribuição pendente',cid,{'motivo':'Responsável do perfil indisponível; equipe deve assumir'},actor='Assistente Sais Blue')
    return person


def repair_waiting_locations(db, audit):
    """Use already received data once, without sending a new WhatsApp message."""
    key='qualification_location_catalog_v2'
    config=settings(db)
    if not config['enabled'] or db.execute('SELECT 1 FROM crm_settings WHERE key=?',(key,)).fetchone():
        return
    for paused in db.execute("SELECT * FROM contacts WHERE ad_origin=1 AND manual_origin=0 AND deleted_at=0 AND owner_id='' AND qualification_state='human'").fetchall():
        latest=db.execute("SELECT id,body,created FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' ORDER BY created DESC,rowid DESC LIMIT 1",(paused['id'],)).fetchone()
        if latest and can_resume_after_reply(db,paused,latest['created'],latest['id']):
            process_answer(db,paused['id'],'recovered-reply:'+latest['id'],latest['body'],latest['created'],audit)
    rows=db.execute("SELECT * FROM contacts WHERE ad_origin=1 AND manual_origin=0 AND deleted_at=0 AND owner_id='' AND qualification_state IN ('waiting_profile','waiting_city')").fetchall()
    for c in rows:
        history=db.execute("SELECT id,body,created FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' ORDER BY created DESC,rowid DESC LIMIT 32",(c['id'],)).fetchall()
        if not history:
            continue
        name,state='', ''
        profile=c['lead_profile']
        for message in reversed(history):
            if not profile:
                profile=parse_profile(message['body']) or ''
            name,state,_=accumulate_location(message['body'],name,state)
        city=CITY_LOOKUP.get((name,state))
        if not city or c['city_id']:
            continue
        cancel_pending(db,c['id'])
        step='completed' if profile else 'waiting_profile'
        db.execute('UPDATE contacts SET city_id=?,city=?,state=?,lead_profile=?,qualification_state=?,updated=?,revision=revision+1 WHERE id=?',
                   (city['id'],city['name'],city['state'],profile,step,time.time(),c['id']))
        db.execute('INSERT OR IGNORE INTO qualification_progress(contact_id,cycle,anchor) VALUES(?,?,?)',(c['id'],'repaired:'+history[0]['id'],history[0]['created']))
        db.execute('UPDATE qualification_progress SET city_text=?,state_text=?,closed_reason=?,next_due=? WHERE contact_id=?',
                   (name,state,'completed' if profile else '',0 if profile else history[0]['created']+REMINDER_OFFSETS[0],c['id']))
        audit(db,'Localização aproveitada do histórico',c['id'],{'cidade':city['name'],'uf':city['state'],'mensagem_enviada':False},actor='Assistente Sais Blue')
        if profile:
            assign_qualified(db,c['id'],c['owner_id'],config,profile,city,audit)
    db.execute('INSERT INTO crm_settings VALUES(?,?)',(key,'done'))


def next_reminder_due(anchor, count, current):
    if count>=len(REMINDER_OFFSETS)+1:
        return 0
    target=anchor+(REMINDER_OFFSETS[count] if count<len(REMINDER_OFFSETS) else FINAL_REMINDER_AFTER)
    floor=current+(REMINDER_OFFSETS[0] if count==0 else MIN_REMINDER_GAP)
    deadline=anchor+FINAL_REMINDER_AFTER
    return min(max(target,floor),deadline) if floor<=deadline else 0


def migrate_cadence(db):
    if not settings(db)['enabled']:
        return
    for p in db.execute('SELECT * FROM qualification_progress WHERE cadence_version=1').fetchall():
        c=db.execute('SELECT * FROM contacts WHERE id=?',(p['contact_id'],)).fetchone()
        active=c['ad_origin'] and not c['manual_origin'] and not c['deleted_at'] and c['qualification_state'] in ('waiting_profile','waiting_city')
        cycle=p['cycle']+':cadence2'
        db.execute("UPDATE messages SET status='cancelled' WHERE contact_id=? AND automation=1 AND automation_kind IN ('reminder','final') AND status='queued'",(c['id'],))
        count=p['reminders_sent']
        due=0
        reason=p['closed_reason']
        if active and not reason:
            sent=db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND automation=1 AND status IN ('accepted','sent','delivered','read','uncertain','sending')",(c['id'],)).fetchone()[0] or p['anchor']
            target=p['anchor']+(REMINDER_OFFSETS[count] if count<len(REMINDER_OFFSETS) else FINAL_REMINDER_AFTER)
            due=max(target,sent+MIN_REMINDER_GAP) if count else max(target,time.time()+REMINDER_OFFSETS[0])
            due=min(due,p['anchor']+FINAL_REMINDER_AFTER)
            if count>=len(REMINDER_OFFSETS)+1:
                due,reason=0,'finished'
            for message in db.execute("SELECT id FROM messages WHERE contact_id=? AND automation=1 AND automation_kind='question' AND status='queued'",(c['id'],)).fetchall():
                text=next_question(c['lead_profile'],p['city_text'],p['state_text'])
                introduced=db.execute("SELECT 1 FROM messages WHERE contact_id=? AND automation=1 AND status IN ('accepted','sent','delivered','read') LIMIT 1",(c['id'],)).fetchone()
                db.execute('UPDATE messages SET body=?,automation_cycle=? WHERE id=?',(('' if introduced else WELCOME)+text,cycle,message['id']))
        db.execute('UPDATE qualification_progress SET cadence_version=2,cycle=?,reminders_sent=?,next_due=?,closed_reason=? WHERE contact_id=?',
                   (cycle,count,due,reason,c['id']))


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
        for message in reversed(db.execute("SELECT body FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' ORDER BY created DESC,rowid DESC LIMIT 12",(c['id'],)).fetchall()):
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
    db.execute('''INSERT OR IGNORE INTO qualification_progress(contact_id,cycle,anchor,next_due,cadence_version)
        SELECT c.id,'legacy:'||c.id,MAX(m.created),MIN(?,MAX(m.created)+?),2
        FROM contacts c JOIN messages m ON m.contact_id=c.id AND m.direction='in' AND m.channel='meta'
        WHERE NOT EXISTS(SELECT 1 FROM qualification_progress p WHERE p.contact_id=c.id) AND c.ad_origin=1 AND c.manual_origin=0 AND c.deleted_at=0 AND c.qualification_state IN ('waiting_profile','waiting_city')
        GROUP BY c.id''',(current+REMINDER_OFFSETS[0],FINAL_REMINDER_AFTER))
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
    final_at=progress['anchor']+FINAL_REMINDER_AFTER
    final=current>=final_at or progress['reminders_sent']>=len(REMINDER_OFFSETS)
    if not final and current>=final_at-MIN_REMINDER_GAP:
        db.execute('UPDATE qualification_progress SET next_due=? WHERE contact_id=?',(final_at,c['id']))
        return
    index=len(REMINDER_OFFSETS)+1 if final else progress['reminders_sent']+1
    reply=reminder_text(c['lead_profile'],progress['city_text'],progress['state_text'],index,final)
    enqueue(db,c['id'],f'reminder:{progress["cycle"]}:{index}',reply,c['qualification_state'],kind='final' if final else 'reminder',cycle=progress['cycle'])
    db.execute('UPDATE qualification_progress SET next_due=0 WHERE contact_id=?',(c['id'],))


def schedule_after_send(db, row):
    progress=db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(row['contact_id'],)).fetchone()
    if not progress or (row['automation_cycle'] and row['automation_cycle']!=progress['cycle']):
        return
    c=db.execute('SELECT qualification_state FROM contacts WHERE id=?',(row['contact_id'],)).fetchone()
    if c['qualification_state'] not in ('waiting_profile','waiting_city'):
        return
    total=len(REMINDER_OFFSETS)+1
    count=total if row['automation_kind']=='final' else progress['reminders_sent']+(1 if row['automation_kind']=='reminder' else 0)
    due=next_reminder_due(progress['anchor'],count,time.time())
    reason='finished' if count>=total else ('window_margin' if not due else '')
    db.execute('UPDATE qualification_progress SET reminders_sent=?,next_due=?,closed_reason=? WHERE contact_id=?',
               (count,due,reason,row['contact_id']))


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
        repair_waiting_locations(db,audit)
        migrate_cadence(db)
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
