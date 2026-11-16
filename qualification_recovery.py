"""Resume stored, unanswered ad messages on the company server, without replaying sends."""
import hashlib
import json
import time

from qualification import (TECHNICAL_PAUSES, WINDOW, LABEL_PROFILE,
    settings, human_intervention_since, process_answer, parse_profile, handover)
from qualification_dialogue import conversation_location, label_details


def optout(body):
    from qualification_location import normalize
    import re
    value=normalize(body)
    return value in ('parar','pare','sair','cancelar','stop') or bool(re.search(r'\bnao (?:quero|desejo) (?:mais |receber )?mensagens\b',value))


def recovery_status(db):
    row=db.execute("SELECT value FROM crm_settings WHERE key='qualification_last_recovery'").fetchone()
    report=json.loads(row['value']) if row else None
    sends={r['status']:r['n'] for r in db.execute('''SELECT m.status,COUNT(*) n FROM qualification_recoveries r
        JOIN messages m ON m.id=r.message_id GROUP BY m.status''')}
    return {'last_run':report,'sends':sends}


def recover_pending(db, audit, *, credentials_ready, trigger='manual'):
    current=time.time()
    report=dict(checked_at=current,trigger=trigger,prepared=0,already_queued=0,already_answered=0,
                expired=0,human=0,uncertain=0,already_attempted=0,blocked='')
    if not settings(db)['enabled']:
        report['blocked']='O primeiro atendimento está desativado em Integrações.'
    elif not credentials_ready:
        report['blocked']='As credenciais de envio da Meta não estão configuradas.'
    else:
        rows=db.execute("""SELECT * FROM contacts WHERE ad_origin=1 AND manual_origin=0 AND deleted_at=0
            AND qualification_state IN ('not_started','waiting_profile','waiting_city','waiting_label','human')
            ORDER BY created,id""").fetchall()
        for c in rows:
            if c['owner_id'] or c['owner']!='Sem responsável' or c['stage']!='Novo contato':
                report['human']+=1;continue
            history=db.execute("""SELECT id,body,created FROM messages WHERE contact_id=? AND direction='in'
                AND channel='meta' ORDER BY created DESC,rowid DESC LIMIT 32""",(c['id'],)).fetchall()
            if not history:continue
            incoming=history[0]
            if current-incoming['created']>=WINDOW:
                report['expired']+=1;continue
            if db.execute('SELECT 1 FROM qualification_recoveries WHERE contact_id=? AND incoming_id=?',(c['id'],incoming['id'])).fetchone():
                report['already_attempted']+=1;continue
            # First attendance only: exclude any registered answer before
            # changing qualification state or interpreting an earlier opt-out.
            outgoing=db.execute("SELECT * FROM messages WHERE contact_id=? AND direction='out' AND channel='meta'",(c['id'],)).fetchall()
            if any(m['status'] in ('accepted','sent','delivered','read') for m in outgoing):
                report['already_answered']+=1;continue
            p=db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone()
            anchor=min(p['anchor'] or incoming['created'],incoming['created']) if p else c['created']
            if any(optout(m['body']) for m in history):
                if c['qualification_state']!='human':
                    handover(db,c['id'],audit,'Cliente pediu para interromper mensagens automáticas')
                report['human']+=1;continue
            if human_intervention_since(db,c['id'],anchor):
                report['human']+=1;continue
            if c['qualification_state']=='human':
                pause=db.execute("SELECT details FROM audit WHERE contact_id=? AND action='Qualificação encaminhada à equipe' ORDER BY id DESC LIMIT 1",(c['id'],)).fetchone()
                reason=json.loads(pause['details']).get('motivo') if pause else ''
                if reason not in TECHNICAL_PAUSES:
                    report['human']+=1;continue
            if any(m['status'] in ('sending','uncertain') for m in outgoing):
                report['uncertain']+=1;continue
            if any(m['status'] in ('queued','pending') for m in outgoing):
                report['already_queued']+=1;continue
            if any(not m['automation'] for m in outgoing):
                report['human']+=1;continue
            # Preserve the answers accumulated before the outage, even when
            # profile, city and UF were sent more than two minutes apart.
            db.execute('INSERT OR IGNORE INTO qualification_progress(contact_id) VALUES(?)',(c['id'],))
            p=db.execute('SELECT * FROM qualification_progress WHERE contact_id=?',(c['id'],)).fetchone()
            profile=c['lead_profile'] or ''
            city,state=p['city_text'] or c['city'],p['state_text'] or c['state']
            details=json.loads(p['label_data'])
            for m in reversed(history):
                if c['qualification_state']!='waiting_label':
                    profile=parse_profile(m['body']) or profile
                    city,state,_=conversation_location(m['body'],city,state)
                if profile==LABEL_PROFILE:details=label_details(m['body'],details)
            db.execute('UPDATE contacts SET lead_profile=? WHERE id=?',(profile,c['id']))
            db.execute('UPDATE qualification_progress SET city_text=?,state_text=?,label_data=? WHERE contact_id=?',
                       (city,state,json.dumps(details,ensure_ascii=False),c['id']))
            if c['qualification_state']=='human':
                step='waiting_label' if profile==LABEL_PROFILE and p['label_asked_at'] else ('waiting_city' if profile else 'waiting_profile')
                db.execute('UPDATE contacts SET qualification_state=? WHERE id=?',(step,c['id']))
            key='recovery:'+incoming['id']
            mid='bot:'+hashlib.sha256(key.encode()).hexdigest()
            # Durable once-per-inbound marker prevents another restart/click
            # from retrying an uncertain or failed recovery send.
            db.execute('INSERT INTO qualification_recoveries VALUES(?,?,?,?)',(c['id'],incoming['id'],mid,current))
            process_answer(db,c['id'],key,incoming['body'],incoming['created'],audit)
            queued=db.execute("SELECT 1 FROM messages WHERE id=? AND status='queued'",(mid,)).fetchone()
            if queued:report['prepared']+=1
            audit(db,'Atendimento pendente revisado para retomada',c['id'],{'preparado_para_envio':bool(queued)},actor='Assistente Sais Blue')
    db.execute("INSERT INTO crm_settings VALUES('qualification_last_recovery',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(report),))
    return report
