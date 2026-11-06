"""Sais Blue CRM: shared team workspace and official WhatsApp adapter."""
import getpass
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import click
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from locations import CITIES, CITY_BY_ID, STATES, location_fields, instagram_handle
from sqlite_context import connection
from qualification import PROFILES, is_ad_referral, settings as qualification_settings, process_answer, process_outbox, handover

ROOT = Path(__file__).parent
STAGES = ['Novo contato', 'Em atendimento', 'Negociação', 'Ganho', 'Perdido']
SESSION_TTL = 12 * 3600
RELEASE = '2026.11.06.5'


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def now():
    return time.time()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def text(value, limit=5000):
    if not isinstance(value, str):
        raise Problem('Informe um texto válido.')
    return value.strip()[:limit]


def phone(value):
    number = re.sub(r'\D', '', str(value))
    if not 10 <= len(number) <= 15:
        raise Problem('Informe o telefone com DDI, entre 10 e 15 dígitos.')
    return number


def email(value):
    value = text(value, 254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise Problem('Informe um e-mail válido.')
    return value


def password(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 256:
        raise Problem('A senha deve ter entre 12 e 256 caracteres.')
    return generate_password_hash(value, method='scrypt')


@contextmanager
def database(app):
    db = sqlite3.connect(app.config['DATABASE'], timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(app):
    with database(app) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL, stage TEXT NOT NULL, value REAL NOT NULL DEFAULT 0, owner TEXT NOT NULL DEFAULT 'Sem responsável', source TEXT NOT NULL, referral TEXT, note TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, contact_id TEXT NOT NULL REFERENCES contacts(id), body TEXT NOT NULL, direction TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','member')), active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS invites(token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, role TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id TEXT, user_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, details TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, until REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS crm_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS messages_contact ON messages(contact_id,created);
        CREATE INDEX IF NOT EXISTS audit_contact ON audit(contact_id,id);
        ''')
        # Additive migration preserves the first prototype's data.
        for table, additions in {
            'contacts': [('revision', 'INTEGER NOT NULL DEFAULT 0'), ('city_id', "TEXT NOT NULL DEFAULT ''"), ('city', "TEXT NOT NULL DEFAULT ''"), ('state', "TEXT NOT NULL DEFAULT ''"), ('instagram', "TEXT NOT NULL DEFAULT ''"), ('ad_origin', 'INTEGER NOT NULL DEFAULT 0'), ('lead_profile', "TEXT NOT NULL DEFAULT ''"), ('qualification_state', "TEXT NOT NULL DEFAULT 'not_started'"), ('qualification_attempts', 'INTEGER NOT NULL DEFAULT 0'), ('qualification_last_at', 'REAL NOT NULL DEFAULT 0')],
            'messages': [('channel', "TEXT NOT NULL DEFAULT 'local'"), ('status', "TEXT NOT NULL DEFAULT ''"), ('external_id', 'TEXT'), ('author', "TEXT NOT NULL DEFAULT ''"), ('error_code','INTEGER'), ('error_detail', "TEXT NOT NULL DEFAULT ''"), ('automation', 'INTEGER NOT NULL DEFAULT 0'), ('automation_step', "TEXT NOT NULL DEFAULT ''"), ('send_started', 'REAL NOT NULL DEFAULT 0')],
        }.items():
            existing = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
            for column, declaration in additions:
                if column not in existing:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS messages_external ON messages(external_id) WHERE external_id IS NOT NULL')
        db.execute('CREATE INDEX IF NOT EXISTS messages_automation ON messages(automation,status,created)')
        for row in db.execute("SELECT id FROM contacts WHERE stage='Proposta enviada'").fetchall():
            db.execute("UPDATE contacts SET stage='Negociação',revision=revision+1,updated=? WHERE id=?", (now(), row['id']))
            db.execute('INSERT INTO audit(contact_id,actor,action,details,created) VALUES(?,?,?,?,?)',
                       (row['id'],'Sistema','Etapa removida do funil',json.dumps({'antes':'Proposta enviada','depois':'Negociação'},ensure_ascii=False),now()))
        for row in db.execute('SELECT id,referral FROM contacts WHERE ad_origin=0 AND referral IS NOT NULL').fetchall():
            try:
                referred = is_ad_referral(json.loads(row['referral']))
            except (ValueError, TypeError):
                referred = False
            if referred:
                db.execute('UPDATE contacts SET ad_origin=1 WHERE id=?', (row['id'],))


def audit(db, action, cid=None, details=None, actor=None):
    user = getattr(g, 'user', None)
    db.execute('INSERT INTO audit(contact_id,user_id,actor,action,details,created) VALUES(?,?,?,?,?,?)',
               (cid, user['id'] if user else None, actor or (user['name'] if user else 'WhatsApp'), action, json.dumps(details or {}, ensure_ascii=False), now()))


def ingest(db, number, name, body, message_id, referral=None, source='WhatsApp', channel='meta', timestamp=None):
    if db.execute('SELECT 1 FROM messages WHERE id=? OR external_id=?', (message_id, message_id)).fetchone():
        return False
    number = phone(number)
    row = db.execute('SELECT id,ad_origin FROM contacts WHERE phone=?', (number,)).fetchone()
    ad_origin = is_ad_referral(referral)
    # A signed ad referral admits the lead; subsequent messages need no repeated referral.
    # Organic conversations never create a card or store message content in this CRM.
    if channel == 'meta' and not ad_origin and not (row and row['ad_origin']):
        return False
    cid = row['id'] if row else secrets.token_hex(12)
    if not row:
        db.execute('INSERT INTO contacts(id,name,phone,stage,source,referral,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                   (cid, name or number, number, STAGES[0], source, json.dumps(referral, ensure_ascii=False) if referral else None, now(), now()))
        audit(db, 'Contato criado', cid, {'source': source})
    elif ad_origin:
        db.execute('UPDATE contacts SET referral=?,source=? WHERE id=?', (json.dumps(referral, ensure_ascii=False), source, cid))
    # Trust the signed event timestamp, never extend the 24-hour window on webhook replay.
    created = min(float(timestamp), now()) if timestamp else now()
    db.execute('INSERT INTO messages(id,contact_id,body,direction,created,channel,external_id) VALUES(?,?,?,?,?,?,?)',
               (message_id, cid, body, 'in', created, channel, message_id if channel == 'meta' else None))
    db.execute('UPDATE contacts SET updated=?,revision=revision+1 WHERE id=?', (now(), cid))
    if ad_origin:
        db.execute('UPDATE contacts SET ad_origin=1 WHERE id=?', (cid,))
    return cid


def meta_failure(code):
    hints={190:'Token inválido ou expirado.',131000:'Erro genérico da Meta; a causa específica não foi informada.',
           131026:'A Meta não conseguiu entregar a mensagem.',131047:'Janela de atendimento encerrada.',
           131030:'Destinatário não autorizado para este número de teste.',133010:'Número não registrado na plataforma da API.',
           100:'Verifique parâmetros, permissões e identificação do recurso.',200:'Permissão de acesso negada.'}
    return hints.get(code,'Falha informada pela Meta; consultar o código no suporte oficial.')


def transmit_meta(app, number, body):
    url = f"https://graph.facebook.com/{app.config['META_API_VERSION']}/{app.config['META_PHONE_NUMBER_ID']}/messages"
    payload = json.dumps({'messaging_product':'whatsapp','to':number,'type':'text','text':{'body':body}}).encode()
    req = urllib.request.Request(url, data=payload, headers={'Authorization':'Bearer '+app.config['META_ACCESS_TOKEN'],'Content-Type':'application/json'})
    external_id, result_status, code = None, 'uncertain', None
    try:
        sender = app.config.get('META_SENDER', urllib.request.urlopen)
        with sender(req, timeout=20) as response:
            external_id = json.load(response)['messages'][0]['id']
        result_status = 'accepted'
    except urllib.error.HTTPError as error:
        result_status = 'failed'
        try:
            code = json.load(error).get('error',{}).get('code')
            code = code if isinstance(code,int) else None
        except (ValueError, TypeError):
            pass
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass  # Never automatically retry: a timeout can follow an accepted request.
    return result_status, external_id, code, meta_failure(code) if code else ''


def run_automation_once(app):
    return process_outbox(app, database, transmit_meta, audit)


def start_automation_worker(app):
    stop = threading.Event()
    def run():
        while not stop.is_set():
            try:
                handled = run_automation_once(app)
            except Exception as exc:
                app.logger.error('Qualification worker: %s', type(exc).__name__)
                handled = False
            if not handled:
                stop.wait(1)
    thread = threading.Thread(target=run, name='saisblue-qualification', daemon=True)
    thread.start()
    return stop, thread


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    production = os.environ.get('APP_ENV') == 'production'
    app.config.update(DATABASE=os.environ.get('CRM_DB', str(ROOT / 'crm.sqlite3')),
                      APP_URL=os.environ.get('APP_URL', '').rstrip('/'),
                      SECURE_COOKIE=production,
                      MAX_CONTENT_LENGTH=1_000_000,
                      META_APP_SECRET=os.environ.get('META_APP_SECRET', ''),
                      META_VERIFY_TOKEN=os.environ.get('META_VERIFY_TOKEN', ''),
                      META_ACCESS_TOKEN=os.environ.get('META_ACCESS_TOKEN', ''),
                      META_PHONE_NUMBER_ID=os.environ.get('META_PHONE_NUMBER_ID', ''),
                      META_API_VERSION=os.environ.get('META_API_VERSION', 'v22.0'),
                      ALLOW_SIMULATION=os.environ.get('ALLOW_SIMULATION', '0') == '1')
    if config:
        app.config.update(config)
    if production and not app.config['APP_URL'].startswith('https://'):
        raise RuntimeError('APP_URL HTTPS é obrigatório em produção.')
    if os.environ.get('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # Backend must only be reachable through the local proxy.
    init_db(app)

    def data():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise Problem('Envie um objeto JSON válido.')
        return value

    def admin():
        if g.user['role'] != 'admin':
            raise Problem('Apenas administradores podem gerenciar acessos.', 403)

    def user_public(u):
        return {k: u[k] for k in ('id', 'email', 'name', 'role', 'active')}

    def session(db, user):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<?', (now(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), user['id'], csrf, now() + SESSION_TTL))
        response = jsonify(user=user_public(user), csrf=csrf)
        response.set_cookie('crm_session', token, max_age=SESSION_TTL, httponly=True, secure=app.config['SECURE_COOKIE'], samesite='Lax', path='/')
        return response

    @app.before_request
    def protect():
        g.user, g.csrf = None, None
        if request.path in ('/api/login', '/api/accept-invite') and request.method == 'POST':
            key = 'public:' + digest(request.remote_addr or 'unknown')
            with database(app) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM attempts WHERE until<?', (now(),))
                row = db.execute('SELECT count FROM attempts WHERE key=?', (key,)).fetchone()
                if row and row['count'] >= 60:
                    raise Problem('Muitas tentativas. Aguarde um minuto.', 429)
                db.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now() + 60))
        # Protect every browser mutation, including login; webhook uses its own signature.
        if request.method == 'POST' and request.path != '/webhooks/whatsapp':
            origin = request.headers.get('Origin')
            expected = app.config['APP_URL'] or request.host_url.rstrip('/')
            if origin and origin != expected:
                raise Problem('Origem não permitida.', 403)
            if not request.is_json:
                raise Problem('Envie JSON.', 415)
        if not request.path.startswith('/api/') or request.path in ('/api/login', '/api/accept-invite'):
            return
        token = request.cookies.get('crm_session', '')
        with database(app) as db:
            row = db.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1', (digest(token), now())).fetchone()
            if not row:
                raise Problem('Entre na sua conta para continuar.', 401)
            g.user, g.csrf = dict(row), row['csrf']
        if request.method == 'POST' and not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), g.csrf):
            raise Problem('Sessão inválida. Atualize a página.', 403)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if app.config['SECURE_COOKIE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, Problem):
            return jsonify(error=exc.message), exc.status
        if isinstance(exc, sqlite3.IntegrityError):
            return jsonify(error='Registro duplicado ou contato inválido.'), 409
        if isinstance(exc, ValueError) and request.path in ('/api/contacts','/api/update','/api/simulate'):
            return jsonify(error=str(exc)), 400
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return jsonify(error='Dados inválidos. Confira os campos.'), 400
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        app.logger.error('Operation failed: %s', type(exc).__name__)
        return jsonify(error='Não foi possível concluir a operação.'), 500

    @app.get('/')
    def index():
        return send_from_directory(ROOT / 'public', 'index.html')

    @app.get('/login')
    def login_page():
        return send_from_directory(ROOT / 'public', 'login.html')

    @app.get('/<name>')
    def asset(name):
        if name not in ('style.css', 'app.js', 'auth.js'):
            raise Problem('Página não encontrada.', 404)
        return send_from_directory(ROOT / 'public', name)

    @app.get('/brand/<name>')
    def brand_asset(name):
        if name not in ('sb-logo.png','montserrat-400.woff2','montserrat-500.woff2','montserrat-600.woff2','montserrat-700.woff2','instrument-serif-italic.woff2'):
            raise Problem('Arquivo não encontrado.',404)
        return send_from_directory(ROOT / 'public/brand',name)

    @app.get('/vendor/leaflet/<path:name>')
    def leaflet_asset(name):
        if name not in ('leaflet.js','leaflet.css','images/layers.png','images/layers-2x.png'):
            raise Problem('Arquivo não encontrado.',404)
        return send_from_directory(ROOT / 'public/vendor/leaflet',name)

    @app.get('/data/brazil-states.geojson')
    def map_boundaries():
        return send_from_directory(ROOT / 'public/data','brazil-states.geojson')

    @app.get('/api/cities')
    def city_catalog():
        return jsonify(cities=CITIES,states=STATES)

    @app.get('/healthz')
    def health():
        with database(app) as db:
            db.execute('SELECT 1').fetchone()
        return jsonify(ok=True, application='sais-blue-crm', version=RELEASE)

    @app.post('/api/login')
    def login():
        d = data()
        address = email(d.get('email', ''))
        key = digest(address + ':' + request.remote_addr)
        # Counters are shared across Gunicorn workers and persisted; no raw emails in keys.
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE until<?', (now(),))
            attempt = db.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
            if attempt and attempt['count'] >= 10:
                raise Problem('Muitas tentativas. Aguarde 15 minutos.', 429)
            db.execute('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1', (key, now() + 900))
            user = db.execute('SELECT * FROM users WHERE email=? AND active=1', (address,)).fetchone()
        supplied = d.get('password', '')
        if not isinstance(supplied, str) or len(supplied) > 256 or not user or not check_password_hash(user['password_hash'], supplied):
            raise Problem('E-mail ou senha incorretos.', 401)
        with database(app) as db:
            db.execute('DELETE FROM attempts WHERE key=?', (key,))
            return session(db, user)

    @app.get('/api/me')
    def me():
        return jsonify(user=user_public(g.user), csrf=g.csrf)

    @app.post('/api/logout')
    def logout():
        with database(app) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(request.cookies.get('crm_session', '')),))
        response = jsonify(ok=True)
        response.delete_cookie('crm_session', path='/')
        return response

    @app.get('/api/team')
    def team():
        with database(app) as db:
            return jsonify(users=[user_public(r) for r in db.execute('SELECT * FROM users ORDER BY name')])

    @app.post('/api/invites')
    def invite():
        admin()
        d = data()
        address, role = email(d.get('email', '')), d.get('role', 'member')
        if role not in ('admin', 'member'):
            raise Problem('Perfil inválido.')
        token = secrets.token_urlsafe(32)
        with database(app) as db:
            existing = db.execute('SELECT id FROM users WHERE email=?', (address,)).fetchone()
            if existing:
                raise Problem('Esse e-mail já tem uma conta. Use redefinir senha.', 409)
            db.execute('DELETE FROM invites WHERE email=?', (address,))
            db.execute('INSERT INTO invites VALUES(?,?,?,?,0)', (digest(token), address, role, now() + 48 * 3600))
            audit(db, 'Convite criado', details={'email': address, 'role': role})
        return jsonify(path='/login#invite=' + token, expires_in=48 * 3600)

    @app.post('/api/accept-invite')
    def accept_invite():
        d = data()
        name = text(d.get('name', ''), 120)
        if not name:
            raise Problem('Informe seu nome.')
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            invitation = db.execute('SELECT * FROM invites WHERE token_hash=? AND used=0 AND expires>?', (digest(text(d.get('token', ''), 200)), now())).fetchone()
            if not invitation:
                raise Problem('Convite inválido, expirado ou já utilizado.', 403)
            hashed = password(d.get('password'))
            db.execute('UPDATE invites SET used=1 WHERE token_hash=?', (invitation['token_hash'],))
            existing = db.execute('SELECT * FROM users WHERE email=?', (invitation['email'],)).fetchone()
            if existing:
                db.execute('UPDATE users SET password_hash=?,name=? WHERE id=?', (hashed, name, existing['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?', (existing['id'],))
            else:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)', (secrets.token_hex(12), invitation['email'], name, hashed, invitation['role'], now()))
            user = db.execute('SELECT * FROM users WHERE email=?', (invitation['email'],)).fetchone()
            if not user['active']:
                raise Problem('Conta desativada. Fale com o administrador.', 403)
            audit(db, 'Acesso ativado', actor=user['name'])
            return session(db, user)

    @app.post('/api/team/update')
    def update_user():
        admin()
        d = data()
        active = d.get('active')
        if not isinstance(active, bool):
            raise Problem('Situação inválida.')
        if d.get('id') == g.user['id']:
            raise Problem('Você não pode desativar a própria conta.')
        with database(app) as db:
            if not db.execute('UPDATE users SET active=? WHERE id=?', (int(active), d.get('id'))).rowcount:
                raise Problem('Pessoa não encontrada.', 404)
            db.execute('DELETE FROM sessions WHERE user_id=?', (d.get('id'),))
            audit(db, 'Acesso alterado', details={'user_id': d.get('id'), 'active': active})
        return jsonify(ok=True)

    @app.post('/api/team/reset')
    def reset_user():
        admin()
        d = data()
        token = secrets.token_urlsafe(32)
        with database(app) as db:
            user = db.execute('SELECT * FROM users WHERE id=? AND active=1', (d.get('id'),)).fetchone()
            if not user:
                raise Problem('Conta não encontrada ou inativa.', 404)
            db.execute('DELETE FROM invites WHERE email=?', (user['email'],))
            db.execute('INSERT INTO invites VALUES(?,?,?,?,0)', (digest(token), user['email'], user['role'], now() + 3600))
            audit(db, 'Redefinição de senha solicitada', details={'user_id': user['id']})
        return jsonify(path='/login#invite=' + token, expires_in=3600)

    @app.get('/api/contacts')
    def contacts():
        with database(app) as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM contacts ORDER BY updated DESC')]
            for row in rows:
                city = CITY_BY_ID.get(row['city_id'])
                row['location_pending'] = city is None
                row['latitude'] = city['lat'] if city else None
                row['longitude'] = city['lng'] if city else None
                row['messages'] = [dict(m) for m in db.execute('SELECT * FROM messages WHERE contact_id=? ORDER BY created,id', (row['id'],))]
                row['audit'] = [dict(a) for a in db.execute('SELECT actor,action,details,created FROM audit WHERE contact_id=? ORDER BY id DESC LIMIT 30', (row['id'],))]
        return jsonify(contacts=rows, stages=STAGES)

    @app.post('/api/contacts')
    def new_contact():
        raise Problem('Novos contatos entram somente por anúncios identificados pela Meta.', 403)

    @app.post('/api/simulate')
    def simulate():
        if not app.config['ALLOW_SIMULATION']:
            raise Problem('Simulações estão desabilitadas neste ambiente.', 403)
        d = data()
        body = text(d.get('body', ''))
        place = location_fields(d['city_id']) if d.get('city_id') else None
        instagram = instagram_handle(d.get('instagram',''))
        if not body:
            raise Problem('Informe a mensagem recebida.')
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            ingest(db, d.get('phone', ''), text(d.get('name', ''), 120), body, secrets.token_hex(16), {'headline': 'Campanha de demonstração Sais Blue', 'source_type': 'ad', 'source_id':'simulation'}, 'Anúncio Meta · simulado', channel='simulation')
            if place:
                db.execute('UPDATE contacts SET city_id=?,city=?,state=?,instagram=? WHERE phone=?', (place['city_id'],place['city'],place['state'],instagram,phone(d.get('phone',''))))
        return jsonify(ok=True)

    @app.post('/api/update')
    def update():
        d = data()
        patch = {key: d[key] for key in ('stage', 'value', 'owner', 'note', 'instagram', 'lead_profile') if key in d}
        if 'city_id' in d:
            patch.update(location_fields(d['city_id']))
        if 'instagram' in patch:
            patch['instagram'] = instagram_handle(patch['instagram'])
        if not patch or not isinstance(d.get('revision'), int):
            raise Problem('Atualize a página antes de editar.')
        if 'stage' in patch and patch['stage'] not in STAGES:
            raise Problem('Etapa inválida.')
        if 'lead_profile' in patch and patch['lead_profile'] not in ('', *PROFILES):
            raise Problem('Selecione Lojista, Revenda ou Consumidor Final.')
        if 'value' in patch:
            patch['value'] = float(patch['value'])
            if not math.isfinite(patch['value']) or not 0 <= patch['value'] <= 1e12:
                raise Problem('Valor inválido.')
        for key in ('owner', 'note'):
            if key in patch:
                patch[key] = text(patch[key], 120 if key == 'owner' else 5000)
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM contacts WHERE id=?', (d.get('id'),)).fetchone()
            if not row:
                raise Problem('Contato não encontrado.', 404)
            if not patch.get('city_id',row['city_id']):
                raise Problem('Preencha cidade e estado na ficha antes de alterar esta oportunidade.')
            if row['revision'] != d['revision']:
                raise Problem('Este card foi atualizado por outra pessoa. Recarregue os dados e revise sua alteração.', 409)
            assignments = ','.join(key + '=?' for key in patch)
            db.execute(f'UPDATE contacts SET {assignments},updated=?,revision=revision+1 WHERE id=?', (*patch.values(), now(), row['id']))
            if patch.get('owner', 'Sem responsável') != 'Sem responsável' or patch.get('stage', STAGES[0]) != STAGES[0]:
                if row['qualification_state'] in ('waiting_profile', 'waiting_city'):
                    handover(db, row['id'], audit, 'Atendimento assumido pela equipe')
            changes = {key: {'antes': row[key], 'depois': value} for key, value in patch.items() if row[key] != value}
            audit(db, 'Oportunidade atualizada', row['id'], changes)
            revision = db.execute('SELECT revision FROM contacts WHERE id=?', (row['id'],)).fetchone()[0]
        return jsonify(ok=True, revision=revision)

    @app.post('/api/claim')
    def claim():
        d = data()
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            c = db.execute('SELECT * FROM contacts WHERE id=?', (d.get('id'),)).fetchone()
            if not c:
                raise Problem('Contato não encontrado.', 404)
            if c['revision'] != d.get('revision'):
                raise Problem('Este card foi atualizado. Recarregue antes de assumir.', 409)
            owner = d.get('owner', g.user['name'])
            if not db.execute('SELECT 1 FROM users WHERE name=? AND active=1', (owner,)).fetchone():
                raise Problem('Selecione uma pessoa ativa da equipe.')
            handover(db, c['id'], audit, 'Transferência para atendimento humano')
            db.execute('UPDATE contacts SET owner=?,stage=? WHERE id=?', (owner, STAGES[1], c['id']))
            audit(db, 'Atendimento assumido', c['id'], {'responsável':owner})
        return jsonify(ok=True)

    @app.post('/api/messages')
    def note():
        d = data()
        body = text(d.get('body', ''))
        if not body:
            raise Problem('Escreva uma nota.')
        with database(app) as db:
            db.execute('INSERT INTO messages(id,contact_id,body,direction,created,author) VALUES(?,?,?,?,?,?)', (secrets.token_hex(16), d.get('id'), body, 'note', now(), g.user['name']))
            db.execute('UPDATE contacts SET updated=? WHERE id=?', (now(), d.get('id')))
            audit(db, 'Nota adicionada', d.get('id'))
        return jsonify(ok=True)

    @app.get('/api/status')
    def status():
        receive = bool(app.config['META_APP_SECRET'] and app.config['META_VERIFY_TOKEN'] and app.config['META_PHONE_NUMBER_ID'])
        sending = bool(receive and app.config['META_ACCESS_TOKEN'])
        with database(app) as db:
            automation = qualification_settings(db)
        return jsonify(version=RELEASE, mode='Equipe Sais Blue', webhook_configured=receive, sending_configured=sending,
                       connection_verified=False, simulation=app.config['ALLOW_SIMULATION'], ads_only=True,
                       manual_contacts_enabled=False, automation=automation, lead_profiles=PROFILES,
                       team_url=app.config['APP_URL'] or request.host_url.rstrip('/'))

    @app.post('/api/automation')
    def configure_automation():
        admin()
        d = data()
        enabled, mode, owners = d.get('enabled'), d.get('assignment_mode', 'regional'), d.get('regional_owners', {})
        if not isinstance(enabled, bool) or mode not in ('manual', 'regional') or not isinstance(owners, dict) or any(not isinstance(owners.get(p,''),str) for p in ('chai','grasi')):
            raise Problem('Configuração de qualificação inválida.')
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            if enabled and mode == 'regional' and any(not db.execute('SELECT 1 FROM users WHERE id=? AND active=1', (owners.get(p,''),)).fetchone() for p in ('chai','grasi')):
                raise Problem('Selecione as contas ativas de Chai e Grasi para a distribuição.')
            if enabled and not (app.config['META_ACCESS_TOKEN'] and app.config['META_PHONE_NUMBER_ID']):
                raise Problem('Configure as credenciais de envio antes de ativar o atendimento automático.')
            config = {'enabled':enabled,'assignment_mode':mode,'regional_owners':{p:owners.get(p,'') for p in ('chai','grasi')}}
            db.execute("INSERT INTO crm_settings VALUES('qualification',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(config),))
            if not enabled:
                for c in db.execute("SELECT id FROM contacts WHERE qualification_state IN ('waiting_profile','waiting_city')").fetchall():
                    handover(db, c['id'], audit, 'Atendimento automático desativado')
                db.execute("UPDATE messages SET status='cancelled' WHERE automation=1 AND status='queued'")
            audit(db, 'Configuração do primeiro atendimento alterada', details=config)
        return jsonify(ok=True, automation=config)

    @app.get('/webhooks/whatsapp')
    def verify():
        token = app.config['META_VERIFY_TOKEN']
        if token and request.args.get('hub.mode') == 'subscribe' and hmac.compare_digest(request.args.get('hub.verify_token', ''), token):
            return request.args.get('hub.challenge', ''), 200, {'Content-Type': 'text/plain'}
        raise Problem('Verificação inválida ou não configurada.', 403)

    @app.post('/webhooks/whatsapp')
    def webhook():
        raw, secret = request.get_data(), app.config['META_APP_SECRET']
        expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not secret or not hmac.compare_digest(request.headers.get('X-Hub-Signature-256', ''), expected):
            raise Problem('Assinatura inválida.', 403)
        payload = data()
        expected_phone = app.config['META_PHONE_NUMBER_ID']
        if not expected_phone:
            raise Problem('Número receptor não configurado.', 503)
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            for entry in payload.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    if str(value.get('metadata', {}).get('phone_number_id', '')) != expected_phone:
                        continue
                    names = {c['wa_id']: c.get('profile', {}).get('name', c['wa_id']) for c in value.get('contacts', [])}
                    for m in value.get('messages', []):
                        body = m.get('text', {}).get('body') or '[' + m.get('type', 'mensagem') + ': mídia recebida; visualização ainda indisponível]'
                        cid = ingest(db, m['from'], names.get(m['from']), body, m['id'], m.get('referral'), 'Anúncio Meta' if is_ad_referral(m.get('referral')) else 'WhatsApp', timestamp=m.get('timestamp'))
                        if cid:
                            created = min(float(m['timestamp']), now()) if m.get('timestamp') else now()
                            process_answer(db, cid, m['id'], body, created, audit)
                    # Ignore older status events after delivered/read; failures remain visible.
                    rank = {'pending': 0, 'uncertain': 0, 'accepted': 1, 'sent': 2, 'delivered': 3, 'read': 4, 'failed': 5}
                    for s in value.get('statuses', []):
                        row = db.execute('SELECT id,status FROM messages WHERE external_id=?', (s.get('id'),)).fetchone()
                        if row and rank.get(s.get('status'), -1) > rank.get(row['status'], 0):
                            error_code=(s.get('errors') or [{}])[0].get('code')
                            error_code=error_code if isinstance(error_code,int) else None
                            db.execute('UPDATE messages SET status=?,error_code=?,error_detail=? WHERE id=?', (s['status'],error_code,meta_failure(error_code) if error_code else '',row['id']))
                            if s['status'] == 'failed':
                                message = db.execute('SELECT contact_id,automation FROM messages WHERE id=?', (row['id'],)).fetchone()
                                if message['automation']:
                                    handover(db, message['contact_id'], audit, 'A Meta informou falha de entrega da mensagem automática')
        return jsonify(ok=True)

    @app.post('/api/send')
    def send():
        d = data()
        token, receiver = app.config['META_ACCESS_TOKEN'], app.config['META_PHONE_NUMBER_ID']
        if not token or not receiver:
            raise Problem('Conecte a conta Meta para enviar mensagens.', 503)
        body, key = text(d.get('body', ''), 4096), text(d.get('request_id', ''), 100)
        if not body or not re.fullmatch(r'[a-zA-Z0-9-]{16,100}', key):
            raise Problem('Mensagem ou identificador inválido.')
        mid = 'out:' + key
        with database(app) as db:
            db.execute('BEGIN IMMEDIATE')
            contact = db.execute('SELECT * FROM contacts WHERE id=?', (d.get('id'),)).fetchone()
            if not contact:
                raise Problem('Contato não encontrado.', 404)
            prior = db.execute('SELECT * FROM messages WHERE id=?', (mid,)).fetchone()
            if prior:
                if prior['contact_id'] != contact['id'] or prior['body'] != body:
                    raise Problem('Identificador já usado para outra mensagem.', 409)
                return jsonify(ok=True, status=prior['status'], duplicate=True)
            last = db.execute("SELECT MAX(created) FROM messages WHERE contact_id=? AND direction='in' AND channel='meta'", (contact['id'],)).fetchone()[0]
            if not last or now() - last >= 24 * 3600:
                raise Problem('Janela de atendimento de 24 horas encerrada. Aguarde uma nova mensagem do cliente; envio por template ainda não disponível.', 409)
            if contact['qualification_state'] in ('waiting_profile', 'waiting_city'):
                handover(db, contact['id'], audit, 'Resposta enviada pela equipe no CRM')
            db.execute('INSERT INTO messages(id,contact_id,body,direction,created,channel,status,author) VALUES(?,?,?,?,?,?,?,?)', (mid, contact['id'], body, 'out', now(), 'meta', 'pending', g.user['name']))
            audit(db, 'Envio solicitado', contact['id'])
        result_status, external_id, error_code, error_detail = transmit_meta(app, contact['phone'], body)
        with database(app) as db:
            db.execute('UPDATE messages SET status=?,external_id=?,error_code=?,error_detail=? WHERE id=?', (result_status,external_id,error_code,error_detail,mid))
            db.execute('UPDATE contacts SET updated=? WHERE id=?', (now(), contact['id']))
        if result_status != 'accepted':
            raise Problem('A Meta recusou o envio.' if result_status == 'failed' else 'Envio sem confirmação. Confira o histórico antes de tentar novamente para evitar duplicação.', 502)
        return jsonify(ok=True, status=result_status)

    @app.cli.command('create-admin')
    @click.option('--email', 'address', required=True)
    @click.option('--name', required=True)
    def create_admin(address, name):
        """Create the first administrator from the server's terminal."""
        hashed = password(getpass.getpass('Senha (mínimo 12 caracteres): '))
        with database(app) as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)', (secrets.token_hex(12), email(address), text(name, 120), hashed, 'admin', now()))
        click.echo('Administrador criado. Entre com o e-mail e a senha escolhidos.')

    @app.cli.command('backup')
    @click.argument('destination')
    def backup(destination):
        """Consistent SQLite backup, including committed WAL records."""
        with database(app) as source, connection(destination) as target:
            source.backup(target)
        os.chmod(destination, 0o600)
        click.echo('Backup criado.')

    return app


app = create_app()
if __name__ == '__main__':
    start_automation_worker(app)
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '3000')), debug=False)
