"""Durable opportunity alerts, restricted to the recipient's current access."""
import time


def _push(db, cid, kind, recipients, event_key, actor_id=None):
    row = db.execute('SELECT deleted_at FROM contacts WHERE id=?', (cid,)).fetchone()
    if not row or row['deleted_at']:
        return
    for uid in set(recipients) - {None, '', actor_id}:
        if db.execute('SELECT 1 FROM users WHERE id=? AND active=1', (uid,)).fetchone():
            db.execute('''INSERT OR IGNORE INTO notifications(user_id,contact_id,kind,event_key,created)
                          VALUES(?,?,?,?,?)''', (uid,cid,kind,event_key,time.time()))


def notify_created(db, cid, actor_id=None):
    row = db.execute('SELECT owner_id FROM contacts WHERE id=?', (cid,)).fetchone()
    admins = [u['id'] for u in db.execute("SELECT id FROM users WHERE role='admin' AND active=1")]
    _push(db,cid,'new',admins+[row['owner_id']],'new:'+cid,actor_id)


def notify_assigned(db, cid, previous_owner, actor_id=None):
    row = db.execute('SELECT owner_id,revision FROM contacts WHERE id=?', (cid,)).fetchone()
    if row['owner_id'] == previous_owner:
        return
    if previous_owner:
        db.execute('UPDATE notifications SET read_at=? WHERE user_id=? AND contact_id=? AND read_at=0', (time.time(),previous_owner,cid))
    _push(db,cid,'assigned',[row['owner_id']],f'assigned:{cid}:{row["revision"]}',actor_id)


def notify_restored(db, cid, actor_id=None):
    row = db.execute('SELECT owner_id,revision FROM contacts WHERE id=?', (cid,)).fetchone()
    _push(db,cid,'restored',[row['owner_id']],f'restored:{cid}:{row["revision"]}',actor_id)
