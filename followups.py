"""Internal follow-up dates and reminders. Never reads credentials or sends WhatsApp."""
import hashlib
import json
import math
import re
import time
from datetime import date, datetime, timedelta, timezone

from notifications import _push
from qualification_location import normalize

LOCAL = timezone(timedelta(hours=-3))
PENDING_STAGE = 'Qualificação pendente'
SEQUENCES = {'Lojista': (0,1,3,7,14,30), 'Revenda': (0,2,5,10,45), 'Consumidor Final': (0,1,3,7,15)}
MODES = {'unset','identification','awaiting','promised','negotiation','customer','paused','closed','blocked'}

def clock():return time.time()

def init(db):
    db.execute('''CREATE TABLE IF NOT EXISTS followups(
        contact_id TEXT PRIMARY KEY REFERENCES contacts(id), version INTEGER NOT NULL DEFAULT 0,
        mode TEXT NOT NULL DEFAULT 'unset', last_conversation_on TEXT NOT NULL DEFAULT '',
        anchor_on TEXT NOT NULL DEFAULT '', next_on TEXT NOT NULL DEFAULT '', next_step TEXT NOT NULL DEFAULT '',
        review_on TEXT NOT NULL DEFAULT '', last_purchase_on TEXT NOT NULL DEFAULT '',
        cycle_days INTEGER NOT NULL DEFAULT 30, progress TEXT NOT NULL DEFAULT '{}',
        response_baseline REAL NOT NULL DEFAULT 0, cycle INTEGER NOT NULL DEFAULT 0,
        updated REAL NOT NULL DEFAULT 0, updated_by TEXT NOT NULL DEFAULT '')''')
    columns={r['name'] for r in db.execute('PRAGMA table_info(followups)')}
    if 'start_step' not in columns:db.execute('ALTER TABLE followups ADD COLUMN start_step INTEGER NOT NULL DEFAULT 0')
    if 'response_rowid' not in columns:
        db.execute('ALTER TABLE followups ADD COLUMN response_rowid INTEGER NOT NULL DEFAULT 0')
        db.execute("UPDATE followups SET response_rowid=COALESCE((SELECT MAX(m.rowid) FROM messages m WHERE m.contact_id=followups.contact_id AND m.direction='in' AND m.channel='meta' AND m.created<=followups.response_baseline),0)")


def day(value):
    if not isinstance(value,str) or len(value)!=10:raise ValueError('Informe uma data válida.')
    try:return date.fromisoformat(value)
    except ValueError:raise ValueError('Informe uma data válida.') from None


def local_day(current):return datetime.fromtimestamp(current,LOCAL).date()


def working_day(value):
    while value.weekday()>4:value+=timedelta(days=1)
    return value


def due_at(value, *, agreed=False):
    target=day(value)
    if not agreed:target=working_day(target)
    return datetime.combine(target,datetime.min.time(),LOCAL).replace(hour=9).timestamp()


def load(db,cid):
    row=db.execute('SELECT * FROM followups WHERE contact_id=?',(cid,)).fetchone()
    return dict(row) if row else dict(contact_id=cid,version=0,mode='unset',last_conversation_on='',anchor_on='',
        next_on='',next_step='',review_on='',last_purchase_on='',cycle_days=30,progress='{}',
        response_baseline=0,cycle=0,updated=0,updated_by='',start_step=0,response_rowid=0)


def latest_incoming(db,cid):
    return db.execute("SELECT COALESCE(MAX(created),0) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'",(cid,)).fetchone()[0]


def incoming_rowid(db,cid):
    return db.execute("SELECT COALESCE(MAX(rowid),0) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'",(cid,)).fetchone()[0]


def snapshot(db,contact,current=None):
    current=clock() if current is None else current
    today=local_day(current);cid=contact['id'];f=load(db,cid)
    f['progress']=json.loads(f['progress'])
    f.update(queue='unscheduled',label='Definir próxima ação',due_on='',due_at=0,overdue=False,plan=[],
             review=False,crm_stage='Novo contato' if contact['stage']==PENDING_STAGE else contact['stage'],purchase_band='',
             last_attempt_on=max(f['progress'].values(),default=''),available_steps=['D'+str(n) for n in SEQUENCES.get(contact['lead_profile'],())])
    mode=f['mode']
    def schedule(queue,label,value,*,agreed=False,review=False):
        f.update(queue=queue,label=label,due_on=value,due_at=due_at(value,agreed=agreed),review=review)
        f['overdue']=local_day(f['due_at'])<today
        f['overdue_days']=max(0,(today-local_day(f['due_at'])).days)
    stopped=False
    for message in db.execute("SELECT body FROM messages WHERE contact_id=? AND direction='in' AND channel='meta' AND created>? ORDER BY created DESC,rowid DESC LIMIT 32",(cid,f['updated'])):
        value=normalize(message['body'])
        if value in ('parar','pare','sair','cancelar','stop') or re.search(r'\bnao (?:quero|desejo) (?:mais |receber )?mensagens\b',value):
            stopped=True;break
    if mode=='blocked' or stopped:f.update(mode='blocked',queue='blocked',label='Não contatar');return f
    if mode=='closed':f.update(queue='closed',label='Tentativa encerrada');return f
    if contact['stage']=='Perdido':
        f.update(queue='closed',label='Perdido · Sem Resposta' if contact['qualification_state']=='no_response' else 'Oportunidade perdida · acompanhamento encerrado');return f
    if contact['stage']=='Ganho' and mode not in ('customer','promised','negotiation'):
        f.update(queue='customer',label='Registrar última compra e ciclo de recompra');return f
    if mode=='unset':return f
    if mode=='identification':
        f.update(queue='identification',label='Identificação nas primeiras 24 horas');return f
    if mode=='paused':
        if f['review_on']:schedule('review','Revisão interna · sem envio automático',f['review_on'],review=True)
        else:f.update(queue='paused',label='Pausado · sem retorno agendado')
        return f
    if mode in ('promised','negotiation'):
        schedule('active','Retorno combinado' if mode=='promised' else f['next_step'],f['next_on'],agreed=True)
        return f
    if mode=='customer':
        if not f['last_purchase_on']:
            f.update(queue='customer',label='Informar data da última compra');return f
        elapsed=(today-day(f['last_purchase_on'])).days;n=f['cycle_days']
        band=next((label for boundary,label in ((n,'No ciclo'),(math.ceil(n*1.5),'Atenção'),(n*2,'Risco'),(n*3,'Inativo')) if elapsed<=boundary),'Dormente')
        f.update(purchase_band=band,purchase_age=elapsed,queue='customer',label=f'{band} · {elapsed} dias desde a compra')
        schedule('customer',f['label'],(day(f['last_purchase_on'])+timedelta(days=n+1)).isoformat(),review=True)
        return f
    if incoming_rowid(db,cid)>f['response_rowid']:
        f.update(queue='conversation',label='Cliente respondeu · defina o próximo passo');return f
    offsets=SEQUENCES.get(contact['lead_profile'])
    if not offsets:
        f.update(queue='unscheduled',label='Definir sequência pelo perfil do cliente');return f
    start=day(f['anchor_on']);start_step=f['start_step'] if f['start_step'] in offsets else 0
    f['start_step']=start_step
    completed={int(k[1:]):day(v) for k,v in f['progress'].items() if k in f['available_steps']}
    latest=max(completed) if completed else None
    for offset in offsets:
        key=f'D{offset}';before_start=offset<start_step
        base=completed[latest] if latest is not None and offset>latest else start
        delta=offset-latest if latest is not None and offset>latest else offset-start_step
        planned=f['progress'].get(key) or ('' if before_start else working_day(base+timedelta(days=delta)).isoformat())
        if offset==offsets[-1] and not f['progress'].get(key) and f['review_on']:
            planned=f['review_on']
        missed=not f['progress'].get(key) and latest is not None and offset<latest
        f['plan'].append(dict(key=key,on=planned,done_on=f['progress'].get(key,''),covered=False,missed=missed,before_start=before_start))
    last=f['plan'][-1]
    if last['done_on']:
        f.update(queue='decision',label='Último retorno realizado · definir Ganho ou Perdido manualmente')
        return f
    remaining=[p for p in f['plan'] if not p['done_on'] and not p['missed'] and not p['before_start']]
    chosen=remaining[0] if remaining else None
    if chosen:
        schedule('active','Contato pertinente · '+chosen['key'],chosen['on']);f['next_key']=chosen['key']
    else:f.update(queue='paused',label='Sequência concluída')
    return f


def save(db,contact,data,actor,current=None):
    current=clock() if current is None else current
    f=load(db,contact['id']);old=dict(f)
    if type(data.get('version')) is not int or data['version']!=f['version']:
        raise RuntimeError('O lembrete foi atualizado. Recarregue o card antes de salvar.')
    if data.get('action')=='record_step':
        keys=['D'+str(n) for n in SEQUENCES.get(contact['lead_profile'],())];key=data.get('step')
        if key not in keys:raise ValueError('Defina o perfil do cliente e selecione uma etapa da sequência.')
        state=snapshot(db,contact,current)
        if state['queue'] in ('blocked','closed','customer') or contact['stage']=='Ganho':
            raise ValueError('Este acompanhamento está encerrado ou bloqueado. Revise a situação antes de iniciar outra tentativa.')
        progress=json.loads(f['progress'])
        offset=int(key[1:]);latest=max((int(k[1:]) for k in progress if k in keys),default=-1)
        if offset<=latest:raise ValueError('Esta etapa já foi ultrapassada. Registre a etapa atual ou inicie uma nova tentativa.')
        if not f['anchor_on']:
            f.update(anchor_on=local_day(current).isoformat(),start_step=offset,cycle=f['cycle']+1)
        progress[key]=local_day(current).isoformat()
        f.update(mode='awaiting',progress=json.dumps(progress),next_on='',next_step='',
                 response_baseline=latest_incoming(db,contact['id']),response_rowid=incoming_rowid(db,contact['id']))
        return persist(db,f,actor,current)
    mode=data.get('mode',f['mode'])
    if mode=='unset' and 'mode' not in data and data.get('last_conversation_on'):
        mode='awaiting' if contact['lead_profile'] in SEQUENCES else 'identification'
    if mode not in MODES:raise ValueError('Selecione uma situação válida.')
    for field in ('last_conversation_on','next_on','review_on','last_purchase_on'):
        if field in data:
            if not isinstance(data[field],str):raise ValueError('Informe uma data válida.')
            value=data[field].strip()
            if value:day(value)
            f[field]=value
    for field in ('last_conversation_on','last_purchase_on'):
        if f[field] and day(f[field])>local_day(current):raise ValueError('A última conversa e a última compra não podem estar no futuro.')
    if 'cycle_days' in data:
        if type(data['cycle_days']) not in (int,str):raise ValueError('Informe o ciclo em dias inteiros.')
        try:cycle=int(data['cycle_days'])
        except (TypeError,ValueError):raise ValueError('Informe o ciclo de recompra em dias.') from None
        if not 1<=cycle<=730:raise ValueError('O ciclo deve ter entre 1 e 730 dias.')
        f['cycle_days']=cycle
    if 'next_step' in data:
        if not isinstance(data['next_step'],str):raise ValueError('Descreva o próximo passo.')
        f['next_step']=data['next_step'].strip()[:500]
    if mode in ('awaiting','identification') and not (f['last_conversation_on'] or (mode=='awaiting' and f['anchor_on'])):
        raise ValueError('Informe a data da última conversa para iniciar o acompanhamento.')
    if mode in ('promised','negotiation') and not f['next_on']:raise ValueError('Informe a data do próximo contato.')
    if mode=='negotiation' and not f['next_step']:raise ValueError('Descreva o próximo passo da negociação.')
    restart=mode=='awaiting' and (old['mode']!='awaiting' or old['last_conversation_on']!=f['last_conversation_on'] or data.get('restart') is True)
    if restart:
        f.update(anchor_on=local_day(current).isoformat() if data.get('restart') is True else f['last_conversation_on'],start_step=0,progress='{}',response_baseline=latest_incoming(db,contact['id']),response_rowid=incoming_rowid(db,contact['id']),cycle=old['cycle']+1)
    if mode=='awaiting' and not SEQUENCES.get(contact['lead_profile']):raise ValueError('Defina Lojista, Revenda ou Consumidor Final para usar a sequência.')
    f['mode']=mode
    if data.get('complete'):
        state=snapshot(db,contact,current)
        key=data['complete']
        if old['mode']!='awaiting' or restart or state['queue']!='active' or key!=state.get('next_key') or day(state['due_on'])>local_day(current):
            raise ValueError('Marque somente a tentativa atual, na data prevista. Se o cliente respondeu, defina o próximo passo.')
        progress=json.loads(f['progress']);progress[key]=local_day(current).isoformat();f['progress']=json.dumps(progress)
    return persist(db,f,actor,current)


def persist(db,f,actor,current):
    f.update(version=f['version']+1,updated=current,updated_by=actor)
    fields=list(f)
    db.execute('INSERT OR REPLACE INTO followups('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(f.values()))
    db.execute("UPDATE notifications SET read_at=? WHERE contact_id=? AND kind IN ('followup','review') AND read_at=0",(current,f['contact_id']))
    return f


def reminders(db,current=None):
    current=clock() if current is None else current
    local=datetime.fromtimestamp(current,LOCAL)
    if local.weekday()>4 or not 9<=local.hour<18:return
    for row in db.execute("SELECT c.* FROM contacts c JOIN followups f ON f.contact_id=c.id WHERE c.deleted_at=0").fetchall():
        c=dict(row);f=snapshot(db,c,current)
        if not f['due_at'] or f['due_at']>current or f['queue'] not in ('active','review','customer'):
            db.execute("UPDATE notifications SET read_at=? WHERE contact_id=? AND kind IN ('followup','review') AND read_at=0",(current,c['id']))
            continue
        if f['queue']=='customer' and f['purchase_band']=='No ciclo':continue
        detail=(f['mode'],f['anchor_on'],f['due_on'],f.get('next_key',''),f['cycle'],f['next_step'],f['purchase_band'])
        token=hashlib.sha256(json.dumps(detail).encode()).hexdigest()[:20]
        recipients=[c['owner_id']] if c['owner_id'] else [u['id'] for u in db.execute("SELECT id FROM users WHERE role='admin' AND active=1")]
        _push(db,c['id'],'review' if f['review'] else 'followup',recipients,'followup:'+c['id']+':'+token)
