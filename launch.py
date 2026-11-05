"""Cross-platform launcher. Config is data, never evaluated as shell code."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED = {'APP_ENV','APP_URL','CRM_DB','ALLOW_SIMULATION','META_APP_SECRET','META_VERIFY_TOKEN',
           'META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_API_VERSION','CRM_DOMAIN'}


def configure(path):
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or key not in ALLOWED:
            raise RuntimeError('Configuração inválida: use apenas as chaves do arquivo de exemplo.')
        os.environ[key] = value.strip()
    db_path = Path(os.environ.get('CRM_DB') or ROOT / 'data' / 'crm.sqlite3')
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ['CRM_DB'] = str(db_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / '.env'))
    parser.add_argument('action', choices=['serve','admin','backup','check'], default='serve', nargs='?')
    parser.add_argument('--email')
    parser.add_argument('--name')
    parser.add_argument('--destination')
    args = parser.parse_args()
    configure(args.config)
    from server import app
    if args.action == 'serve':
        from waitress import serve
        serve(app, host='127.0.0.1', port=3000, threads=8, connection_limit=100,
              channel_timeout=30, max_request_body_size=1_000_000,
              trusted_proxy='127.0.0.1', trusted_proxy_count=1,
              trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'})
    elif args.action == 'admin':
        if not args.email or not args.name:
            parser.error('Informe --email e --name.')
        with app.app_context():
            app.cli.main(args=['create-admin', '--email', args.email, '--name', args.name], prog_name='saisblue', standalone_mode=False)
    elif args.action == 'backup':
        if not args.destination:
            parser.error('Informe --destination.')
        with app.app_context():
            app.cli.main(args=['backup', args.destination], prog_name='saisblue', standalone_mode=False)
    else:
        with app.test_client() as client:
            assert client.get('/healthz').status_code == 200
        print('Configuração e banco acessíveis. A conexão real com a Meta ainda precisa ser validada.')
