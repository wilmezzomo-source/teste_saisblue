"""Private, paginated CRM read model. Original records remain authoritative."""
import hashlib
import json
import math
from datetime import timedelta

import followups
from locations import CITY_BY_ID

STAGES=('Novo contato','Em atendimento','Negociação','Ganho','Perdido')
PAGE_SIZE=30
FIELDS=('id','name','phone','stage','value','owner','owner_id','source','created','updated','revision',
        'city_id','city','state','instagram','ad_origin','manual_origin','lead_profile','qualification_state')


def init(db,revision):
    previous=db.execute("SELECT value FROM crm_settings WHERE key='workspace_read_model'").fetchone()
    rebuild=not previous or previous['value']!=revision
    if rebuild:
        for trigger in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'workspace_%'").fetchall():
            db.execute('DROP TRIGGER "'+trigger['name'].replace('"','""')+'"')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS workspace_versions(scope TEXT PRIMARY KEY,version INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS workspace_dirty(contact_id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS workspace_activity(
      contact_id TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
      total INTEGER NOT NULL DEFAULT 0,incoming INTEGER NOT NULL DEFAULT 0,last_incoming REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS workspace_cards(
      contact_id TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
      summary TEXT NOT NULL,followup TEXT NOT NULL,queue TEXT NOT NULL,
      due_on TEXT NOT NULL,due_at REAL NOT NULL,incoming_count INTEGER NOT NULL,
      message_count INTEGER NOT NULL,last_message_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS workspace_due ON workspace_cards(queue,due_at);
    CREATE INDEX IF NOT EXISTS contacts_owner_updated ON contacts(owner_id,updated DESC,id) WHERE deleted_at=0;
    CREATE INDEX IF NOT EXISTS contacts_stage_updated ON contacts(stage,updated DESC,id) WHERE deleted_at=0;
    CREATE INDEX IF NOT EXISTS contacts_updated ON contacts(updated DESC,id) WHERE deleted_at=0;
    CREATE INDEX IF NOT EXISTS contacts_qualification ON contacts(qualification_state,stage,owner_id) WHERE deleted_at=0 AND ad_origin=1 AND manual_origin=0;
    CREATE INDEX IF NOT EXISTS messages_incoming ON messages(contact_id,created DESC) WHERE direction='in' AND channel='meta';
    CREATE INDEX IF NOT EXISTS messages_incoming_order ON messages(contact_id) WHERE direction='in' AND channel='meta';
    CREATE INDEX IF NOT EXISTS messages_bot ON messages(contact_id,created DESC) WHERE automation=1;
    CREATE INDEX IF NOT EXISTS qualification_label_due ON qualification_progress(label_due) WHERE label_due>0;
    CREATE INDEX IF NOT EXISTS qualification_anchor ON qualification_progress(anchor) WHERE anchor>0;
    ''')
    db.execute("""INSERT OR IGNORE INTO workspace_activity
      SELECT c.id,COUNT(m.id),COALESCE(SUM(m.direction='in'),0),COALESCE(MAX(CASE WHEN m.direction='in' AND m.channel='meta' THEN m.created END),0)
      FROM contacts c LEFT JOIN messages m ON m.contact_id=c.id
      WHERE NOT EXISTS(SELECT 1 FROM workspace_activity a WHERE a.contact_id=c.id) GROUP BY c.id""")
    increase="""INSERT INTO workspace_activity VALUES(NEW.contact_id,1,NEW.direction='in',CASE WHEN NEW.direction='in' AND NEW.channel='meta' THEN NEW.created ELSE 0 END)
      ON CONFLICT(contact_id) DO UPDATE SET total=total+1,incoming=incoming+(NEW.direction='in'),last_incoming=MAX(last_incoming,excluded.last_incoming);"""
    decrease="""UPDATE workspace_activity SET total=total-1,incoming=incoming-(OLD.direction='in'),
      last_incoming=CASE WHEN OLD.direction='in' AND OLD.channel='meta' AND OLD.created>=last_incoming THEN
        COALESCE((SELECT MAX(created) FROM messages WHERE contact_id=OLD.contact_id AND direction='in' AND channel='meta'),0) ELSE last_incoming END
      WHERE contact_id=OLD.contact_id;"""
    db.executescript(f'''
      CREATE TRIGGER IF NOT EXISTS workspace_activity_contact_insert AFTER INSERT ON contacts BEGIN
        INSERT OR IGNORE INTO workspace_activity(contact_id) VALUES(NEW.id); END;
      CREATE TRIGGER IF NOT EXISTS workspace_activity_message_insert AFTER INSERT ON messages BEGIN {increase} END;
      CREATE TRIGGER IF NOT EXISTS workspace_activity_message_delete AFTER DELETE ON messages BEGIN {decrease} END;
      CREATE TRIGGER IF NOT EXISTS workspace_activity_message_update AFTER UPDATE ON messages
        WHEN OLD.contact_id<>NEW.contact_id OR OLD.direction<>NEW.direction OR OLD.channel<>NEW.channel OR OLD.created<>NEW.created
        BEGIN {decrease} {increase} END;
    ''')
    # Tiny triggers invalidate only the affected contact and access scopes.
    # They use built-in SQLite operations, including for older Windows tools.
    for table in ('contacts','messages','audit','followups','qualification_progress'):
        for operation in ('INSERT','UPDATE','DELETE'):
            ref='OLD' if operation=='DELETE' else 'NEW'
            cid=f'{ref}.id' if table=='contacts' else f'{ref}.contact_id'
            owner=f'{ref}.owner_id' if table=='contacts' else f'(SELECT owner_id FROM contacts WHERE id={cid})'
            dirty=(f'DELETE FROM workspace_cards WHERE contact_id={cid}; DELETE FROM workspace_dirty WHERE contact_id={cid};'
                   if table=='contacts' and operation=='DELETE' else
                   f'INSERT OR IGNORE INTO workspace_dirty SELECT {cid} WHERE {cid} IS NOT NULL;')
            old_scope=''
            if table=='contacts' and operation=='UPDATE':
                old_scope="INSERT INTO workspace_versions VALUES('user:'||OLD.owner_id,1) ON CONFLICT(scope) DO UPDATE SET version=version+1;"
            elif operation=='UPDATE':
                old_scope="INSERT OR IGNORE INTO workspace_dirty SELECT OLD.contact_id WHERE OLD.contact_id IS NOT NULL AND OLD.contact_id<>NEW.contact_id; INSERT INTO workspace_versions VALUES('user:'||COALESCE((SELECT owner_id FROM contacts WHERE id=OLD.contact_id),''),1) ON CONFLICT(scope) DO UPDATE SET version=version+1;"
            db.executescript(f'''CREATE TRIGGER IF NOT EXISTS workspace_{table}_{operation.lower()} AFTER {operation} ON {table}
              BEGIN {dirty}
              INSERT INTO workspace_versions VALUES('*',1) ON CONFLICT(scope) DO UPDATE SET version=version+1;
              INSERT INTO workspace_versions VALUES('user:'||COALESCE({owner},''),1) ON CONFLICT(scope) DO UPDATE SET version=version+1;
              {old_scope} END;''')
    db.execute('INSERT OR IGNORE INTO workspace_dirty SELECT id FROM contacts WHERE deleted_at=0 AND NOT EXISTS(SELECT 1 FROM workspace_cards w WHERE w.contact_id=contacts.id)')
    if rebuild:
        db.execute('INSERT OR IGNORE INTO workspace_dirty SELECT id FROM contacts WHERE deleted_at=0')
        db.execute('UPDATE workspace_versions SET version=version+1')
        db.execute("INSERT INTO crm_settings VALUES('workspace_read_model',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(revision,))


def refresh(db):
    """Refresh changed cards in the caller's write transaction; never touch history."""
    for dirty in db.execute('SELECT contact_id FROM workspace_dirty').fetchall():
        cid=dirty['contact_id'];row=db.execute('SELECT * FROM contacts WHERE id=?',(cid,)).fetchone()
        if not row or row['deleted_at']:
            db.execute('DELETE FROM workspace_cards WHERE contact_id=?',(cid,))
        else:
            c=dict(row);city=CITY_BY_ID.get(c['city_id']);summary={key:c[key] for key in FIELDS}
            summary.update(location_pending=city is None,latitude=city['lat'] if city else None,longitude=city['lng'] if city else None)
            counts=db.execute('SELECT total,incoming,last_incoming FROM workspace_activity WHERE contact_id=?',(cid,)).fetchone()
            last=db.execute('SELECT substr(body,1,320) AS body,created,direction FROM messages WHERE contact_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(cid,)).fetchone()
            summary.update(incoming_count=counts['incoming'],message_count=counts['total'],last_message=dict(last) if last else None,latest_incoming_at=counts['last_incoming'] or 0)
            f=followups.snapshot(db,c)
            db.execute('INSERT OR REPLACE INTO workspace_cards VALUES(?,?,?,?,?,?,?,?,?)',
                       (cid,json.dumps(summary,ensure_ascii=False),json.dumps(f,ensure_ascii=False),f['queue'],f['due_on'],f['due_at'],counts['incoming'],counts['total'],last['created'] if last else 0))
        db.execute('DELETE FROM workspace_dirty WHERE contact_id=?',(cid,))


def tag(db,user,args,revision):
    scope='*' if user['role']=='admin' else 'user:'+user['id']
    version=db.execute('SELECT version FROM workspace_versions WHERE scope=?',(scope,)).fetchone()
    value=(revision,user['id'],user['role'],version['version'] if version else 0,followups.local_day(followups.clock()).isoformat(),sorted(args.items()))
    return hashlib.sha256(json.dumps(value,ensure_ascii=False).encode()).hexdigest()


def serialized(row,current=None):
    c=json.loads(row['summary']);f=json.loads(row['followup']);today=followups.local_day(followups.clock() if current is None else current)
    if f['due_at']:
        f['overdue_days']=max(0,(today-followups.local_day(f['due_at'])).days);f['overdue']=f['overdue_days']>0
    if f['queue']=='customer' and f['last_purchase_on']:
        elapsed=(today-followups.day(f['last_purchase_on'])).days;n=f['cycle_days']
        band=next((label for boundary,label in ((n,'No ciclo'),(math.ceil(n*1.5),'Atenção'),(n*2,'Risco'),(n*3,'Inativo')) if elapsed<=boundary),'Dormente')
        f.update(purchase_band=band,purchase_age=elapsed,label=f'{band} · {elapsed} dias desde a compra')
    c['followup']=f
    return c


def integer(value,default=0,maximum=1000000):
    try:return min(maximum,max(0,int(value)))
    except (ValueError,TypeError):return default


def conditions(user,args,*,date=True,search=False):
    sql=['c.deleted_at=0'];values=[]
    if user['role']!='admin':sql.append('c.owner_id=?');values.append(user['id'])
    profile=args.get('profile','')
    if profile:sql.append('c.lead_profile=?');values.append('' if profile=='__pending__' else profile)
    owner=args.get('owner','')
    if owner:sql.append('c.owner_id=?');values.append('' if owner=='__unassigned__' else owner)
    if args.get('city'):sql.append('c.city_id=?');values.append(args['city'])
    if args.get('filter_stage') in STAGES:sql.append('c.stage=?');values.append(args['filter_stage'])
    today=followups.local_day(followups.clock());kind=args.get('date','all')
    if date:
        if kind=='none':sql.append("w.due_on='' AND w.queue NOT IN ('blocked','closed','decision')")
        elif kind=='overdue':sql.append("w.queue='active' AND w.due_at>0 AND w.due_at<?");values.append(followups.due_at(today.isoformat(),agreed=True))
        elif kind in ('today','tomorrow'):
            sql.append("w.queue='active' AND w.due_on=?");values.append((today+timedelta(days=kind=='tomorrow')).isoformat())
        elif kind=='week':
            sql.append("w.queue='active' AND w.due_on BETWEEN ? AND ?");values.extend((today.isoformat(),(today+timedelta(days=7)).isoformat()))
        elif kind=='range':
            for key,operator in (('from','>='),('to','<=')):
                if args.get(key):followups.day(args[key]);sql.append('w.due_on<>\'\' AND w.due_on'+operator+'?');values.append(args[key])
    if search and args.get('q'):
        # Literal substring, including phone formatting as the original search.
        sql.append("instr(casefold(c.name||' '||c.phone||' '||c.source||' '||c.owner||' '||c.city||' '||c.state||' '||c.instagram||' '||c.lead_profile),casefold(?))>0")
        values.append(args['q'][:250])
    return ' AND '.join(sql),values


def queue_condition(key):
    today=followups.local_day(followups.clock()).isoformat();start=followups.due_at(today,agreed=True)
    return {
      'all':('1',[]),'work':("w.queue='active' AND w.due_on<=?",[today]),
      'today':("w.queue='active' AND w.due_on=?",[today]),
      'late':("w.queue='active' AND w.due_at>0 AND w.due_at<?",[start]),
      'scheduled':("w.queue='active' AND w.due_on>?",[today]),
      'unscheduled':("w.queue IN ('unscheduled','identification','conversation')",[]),
      **{key:('w.queue=?',[key]) for key in ('decision','review','customer','paused','closed','blocked')}
    }.get(key,('0',[]))


FROM=' FROM contacts c JOIN workspace_cards w ON w.contact_id=c.id WHERE '


def stats(db,user,args):
    where,values=conditions(user,args)
    row=dict(db.execute("SELECT COUNT(*) AS total,COALESCE(SUM(c.stage NOT IN ('Ganho','Perdido')),0) AS open,COALESCE(SUM(c.stage='Ganho'),0) AS won,COALESCE(SUM(CASE WHEN c.stage NOT IN ('Ganho','Perdido') THEN c.value ELSE 0 END),0) AS open_value,COALESCE(SUM(CASE WHEN c.stage='Ganho' THEN c.value ELSE 0 END),0) AS won_value,COALESCE(SUM(w.incoming_count>0),0) AS inbox"+FROM+where,values).fetchone())
    row['profiles']=[dict(r) for r in db.execute("SELECT c.lead_profile AS profile,COUNT(*) AS total,SUM(c.stage NOT IN ('Ganho','Perdido')) AS open,SUM(c.stage='Ganho') AS won,SUM(CASE WHEN c.stage NOT IN ('Ganho','Perdido') THEN c.value ELSE 0 END) AS open_value,SUM(CASE WHEN c.stage='Ganho' THEN c.value ELSE 0 END) AS won_value"+FROM+where+' GROUP BY c.lead_profile',values)]
    row['stages']={r['stage']:dict(r) for r in db.execute('SELECT c.stage,COUNT(*) AS total,SUM(c.value) AS value'+FROM+where+' GROUP BY c.stage',values)}
    row['sources']=[dict(r) for r in db.execute('SELECT c.source,COUNT(*) AS total'+FROM+where+' GROUP BY c.source',values)]
    row['due']=db.execute('SELECT COUNT(*)'+FROM+where+" AND w.queue='active' AND w.due_on<=?",(*values,followups.local_day(followups.clock()).isoformat())).fetchone()[0]
    base,base_values=conditions(user,args,date=False)
    expressions=[];queue_values=[]
    for key in ('all','work','today','late','scheduled','unscheduled','decision','review','customer','paused','closed','blocked'):
        queue,params=queue_condition(key)
        expressions.append('COALESCE(SUM(CASE WHEN '+queue+' THEN 1 ELSE 0 END),0) AS "'+key+'"');queue_values.extend(params)
    row['queues']=dict(db.execute('SELECT '+','.join(expressions)+FROM+base,(*queue_values,*base_values)).fetchone())
    return row


def page(db,user,args):
    view=args.get('view','pipeline');where,values=conditions(user,args,search=True)
    result={'contacts':[],'stages':STAGES,'stats':stats(db,user,args),'pages':{}}
    if view in ('settings','team','reports','trash'):return result
    if view=='pipeline':
        try:pages=json.loads(args.get('pages','{}'))
        except (ValueError,TypeError):pages={}
        if not isinstance(pages,dict):pages={}
        for stage in STAGES:
            sql=where+' AND c.stage=?';params=(*values,stage)
            totals=db.execute('SELECT COUNT(*),COALESCE(SUM(c.value),0)'+FROM+sql,params).fetchone()
            total,value=totals
            p=min(integer(pages.get(stage)),max(0,(total-1)//PAGE_SIZE))
            result['pages'][stage]={'page':p,'total':total,'size':PAGE_SIZE,'value':value}
            rows=db.execute('SELECT w.*'+FROM+sql+' ORDER BY c.updated DESC,c.id LIMIT ? OFFSET ?',(*params,PAGE_SIZE,p*PAGE_SIZE))
            result['contacts'].extend(serialized(r) for r in rows)
    elif view=='map':
        map_sql=where;map_values=list(values)
        for key,col in (('state','state'),('stage','stage')):
            if args.get(key):map_sql+=' AND c.'+col+'=?';map_values.append(args[key])
        groups=[dict(r) for r in db.execute('SELECT c.city_id,c.city,c.state,COUNT(*) AS total'+FROM+map_sql+" AND json_extract(w.summary,'$.location_pending')=0 GROUP BY c.city_id,c.city,c.state ORDER BY total DESC,c.city",map_values)]
        result['map_groups']=[]
        for group in groups:
            city=CITY_BY_ID.get(group['city_id'])
            if city:group.update(latitude=city['lat'],longitude=city['lng']);result['map_groups'].append(group)
        result['map_total']=sum(g['total'] for g in result['map_groups'])
        pending_sql=where+" AND json_extract(w.summary,'$.location_pending')=1"
        result['pending_total']=db.execute('SELECT COUNT(*)'+FROM+pending_sql,values).fetchone()[0]
        try:pages=json.loads(args.get('pages','{}'))
        except (ValueError,TypeError):pages={}
        p=min(integer(pages.get('pending')) if isinstance(pages,dict) else 0,max(0,(result['pending_total']-1)//PAGE_SIZE))
        result['pages']['pending']={'page':p,'size':PAGE_SIZE,'total':result['pending_total']}
        result['contacts']=[serialized(r) for r in db.execute('SELECT w.*'+FROM+pending_sql+' ORDER BY c.updated DESC,c.id LIMIT ? OFFSET ?',(*values,PAGE_SIZE,p*PAGE_SIZE))]
    else:
        if view=='inbox':where+=' AND w.message_count>0'
        if view=='followups':
            queue,params=queue_condition(args.get('queue','work'));where+=' AND '+queue;values.extend(params)
        total=db.execute('SELECT COUNT(*)'+FROM+where,values).fetchone()[0]
        p=min(integer(args.get('page')),max(0,(total-1)//PAGE_SIZE));order="CASE WHEN w.due_at=0 THEN 1 ELSE 0 END,w.due_at,c.id" if view=='followups' else 'w.last_message_at DESC,c.id' if view=='inbox' else 'c.updated DESC,c.id'
        result['pages']['list']={'page':p,'total':total,'size':PAGE_SIZE}
        result['contacts']=[serialized(r) for r in db.execute('SELECT w.*'+FROM+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',(*values,PAGE_SIZE,p*PAGE_SIZE))]
    return result
