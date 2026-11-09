"""Encrypted, durable Web Push. Provider endpoints and current access are checked."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

PROVIDERS = {'web.push.apple.com', 'fcm.googleapis.com', 'updates.push.services.mozilla.com'}


def key_path(app):
    return Path(app.config['PUSH_KEY_FILE'])


def _read_key(path):
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != 'secp256r1':
        raise ValueError('A chave de notificações existente precisa de revisão. Ela não foi substituída.')
    return key


def public_key(app, create=False):
    path = key_path(app)
    if not path.is_file():
        if not create:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        key = ec.generate_private_key(ec.SECP256R1())
        encoded = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        temporary = path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
        try:
            with temporary.open('xb') as output:
                os.chmod(temporary, 0o600)
                output.write(encoded)
            try:
                os.link(temporary, path)  # Atomic create; a concurrent request cannot rotate an existing key.
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    key = _read_key(path)
    raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def _decode(value, length):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}',value):
        raise ValueError('A inscrição de notificações é inválida.')
    raw = base64.urlsafe_b64decode(value.rstrip('=')+'='*((-len(value.rstrip('=')))%4))
    if len(raw) != length:
        raise ValueError('A inscrição de notificações é inválida.')
    return raw


def validate_subscription(value):
    if not isinstance(value,dict) or not isinstance(value.get('endpoint'),str):
        raise ValueError('A inscrição de notificações é inválida.')
    endpoint = value['endpoint']
    if len(endpoint)>4096 or any(c.isspace() or ord(c)<32 for c in endpoint):
        raise ValueError('O endereço de notificações é inválido.')
    url = urlsplit(endpoint)
    if url.scheme!='https' or url.hostname not in PROVIDERS or url.port not in (None,443) or url.username or url.password or url.fragment or not url.path.strip('/'):
        raise ValueError('O provedor de notificações não é permitido.')
    keys = value.get('keys')
    if not isinstance(keys,dict):
        raise ValueError('A inscrição de notificações é inválida.')
    point = _decode(keys.get('p256dh'),65)
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),point)
    _decode(keys.get('auth'),16)
    return {'endpoint':endpoint,'p256dh':keys['p256dh'],'auth':keys['auth']}


def enqueue_notification(db, nid, uid):
    for sub in db.execute('SELECT id FROM push_subscriptions WHERE user_id=? AND enabled=1',(uid,)).fetchall():
            db.execute('''INSERT OR IGNORE INTO push_deliveries(notification_id,subscription_id,user_id,kind,created,next_try)
                      VALUES(?,?,?,'lead',?,?)''',(nid,sub['id'],uid,time.time(),time.time()))


def process_push_once(app, connect):
    with app.app_context(), connect(app) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE push_deliveries SET state='queued',next_try=? WHERE state='sending' AND updated<? AND attempts<4",(time.time()+30,time.time()-120))
        db.execute("UPDATE push_deliveries SET state='failed',last_error='interrupted' WHERE state='sending' AND updated<? AND attempts>=4",(time.time()-120,))
        row = db.execute('''SELECT d.*,s.user_id AS subscription_user_id,s.endpoint,s.p256dh,s.auth,s.enabled,u.active,u.role
            FROM push_deliveries d JOIN push_subscriptions s ON s.id=d.subscription_id JOIN users u ON u.id=s.user_id
            WHERE d.state='queued' AND d.next_try<=? ORDER BY d.id LIMIT 1''',(time.time(),)).fetchone()
        if not row:
            return False
        row = dict(row)
        permitted = row['enabled'] and row['active'] and row['user_id']==row['subscription_user_id']
        if row['notification_id'] is not None:
            notice = db.execute('''SELECT n.user_id,n.read_at,c.deleted_at,c.owner_id FROM notifications n
                JOIN contacts c ON c.id=n.contact_id WHERE n.id=?''',(row['notification_id'],)).fetchone()
            permitted = permitted and notice and notice['user_id']==row['user_id'] and not notice['read_at'] and not notice['deleted_at'] and (row['role']=='admin' or notice['owner_id']==row['user_id'])
        if not permitted or not public_key(app):
            db.execute("UPDATE push_deliveries SET state='cancelled',updated=? WHERE id=?",(time.time(),row['id']))
            return True
        db.execute("UPDATE push_deliveries SET state='sending',attempts=attempts+1,updated=? WHERE id=?",(time.time(),row['id']))
    # Never hold a database transaction during an outbound request.
    nid = row['notification_id']
    payload = {'title':'Novo lead no CRM' if nid else 'Teste Sais Blue CRM',
               'body':'Há uma nova oportunidade para acompanhar. Toque para abrir o CRM.' if nid else 'As notificações deste aparelho estão funcionando.',
               'notice':nid,'tag':f'crm-notice:{nid}' if nid else f'crm-test:{row["id"]}'}
    topic = hashlib.sha256(f'{row["subscription_id"]}:{nid or "test"}:{row["id"]}'.encode()).hexdigest()[:32]
    state, error, retry, disabled = 'sent','',0,False
    try:
        sender = app.config.get('PUSH_SENDER') or webpush
        sender(subscription_info={'endpoint':row['endpoint'],'keys':{'p256dh':row['p256dh'],'auth':row['auth']}},
               data=json.dumps(payload,ensure_ascii=False),vapid_private_key=str(key_path(app)),
               vapid_claims={'sub':app.config['PUSH_SUBJECT']},ttl=3600,timeout=10,
               headers={'Topic':topic,'Urgency':'high'})
    except WebPushException as exc:
        code = getattr(exc.response,'status_code',None)
        error = 'http_'+str(code) if isinstance(code,int) else 'provider_error'
        disabled = code in (404,410)
        state = 'expired' if disabled else 'failed'
        if code in (429,500,502,503,504) and row['attempts']<3:
            state,retry = 'queued',[30,120,600][row['attempts']]
    except Exception:
        error = 'network_or_configuration'
        state = 'queued' if row['attempts']<3 else 'failed'
        retry = [30,120,600][row['attempts']] if state=='queued' else 0
    with app.app_context(), connect(app) as db:
        db.execute('UPDATE push_deliveries SET state=?,last_error=?,next_try=?,updated=? WHERE id=?',(state,error,time.time()+retry,time.time(),row['id']))
        if disabled:
            db.execute('UPDATE push_subscriptions SET enabled=0 WHERE id=? AND user_id=?',(row['subscription_id'],row['user_id']))
    return True


def start_push_worker(app, connect, stop):
    def run():
        while not stop.is_set():
            try:
                handled = process_push_once(app,connect)
            except Exception as exc:
                app.logger.error('Push worker: %s',type(exc).__name__)
                handled = False
            if not handled:
                stop.wait(1)
    worker = threading.Thread(target=run,name='saisblue-push',daemon=True)
    worker.start()
    return worker
