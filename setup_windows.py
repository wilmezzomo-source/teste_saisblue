"""Interactive local Windows bootstrap. No default account or remote access agent."""
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / '.venv' / 'Scripts' / 'python.exe'


def run(arguments, **kwargs):
    return subprocess.run([str(x) for x in arguments], cwd=ROOT, check=True, **kwargs)


def backend(code, payload=None):
    # Password only goes through the child process pipe, never argv, logs or a file.
    result = run([PYTHON, '-c', code], input=json.dumps(payload or {}), capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)


def main():
    if sys.platform != 'win32':
        raise RuntimeError('Execute este assistente no servidor Windows. Consulte README para outros sistemas.')
    if sys.version_info < (3, 12):
        raise RuntimeError('Instale Python 3.12 ou superior com o launcher py e execute novamente.')
    if str(ROOT).startswith('\\\\'):
        raise RuntimeError('Extraia em disco local, por exemplo C:\\SaisBlueCRM. Nao use pasta de rede.')
    print('\nSAIS BLUE CRM — preparação do Windows\n')
    print('Este assistente instala dependências nesta pasta, prepara o banco local e cria seu acesso.')
    print('Não modifica DNS, site, e-mails ou WhatsApp. Não instala acesso remoto.\n')
    if not PYTHON.exists():
        print('Criando o ambiente Python...')
        run([sys.executable, '-m', 'venv', ROOT / '.venv'])
    print('Conferindo e instalando as dependências (requer internet)...')
    run([PYTHON, '-m', 'pip', 'install', '-r', ROOT / 'requirements.txt'])
    config = ROOT / '.env'
    if not config.exists():
        config.write_text('APP_ENV=development\nAPP_URL=http://127.0.0.1:3000\nCRM_DOMAIN=\nCRM_DB=data/crm.sqlite3\nALLOW_SIMULATION=1\nMETA_APP_SECRET=\nMETA_VERIFY_TOKEN=\nMETA_ACCESS_TOKEN=\nMETA_PHONE_NUMBER_ID=\nMETA_API_VERSION=v22.0\n', encoding='utf-8')
        print('\nConfiguração inicial criada para teste apenas neste computador.')
    else:
        print('\nMantendo a configuração .env já existente.')
    common = "from launch import configure; configure('.env'); from server import app,database,password,email,text; "
    count = backend(common + "\nwith database(app) as db:\n print(__import__('json').dumps({'admins':db.execute(\"SELECT COUNT(*) FROM users WHERE role='admin' AND active=1\").fetchone()[0]}))")
    if not count['admins']:
        print('\nVamos criar seu acesso de administrador. Não existe senha padrão.')
        name = input('Seu nome: ').strip()
        address = input('Seu e-mail corporativo: ').strip()
        if not name or '@' not in address:
            raise RuntimeError('Informe nome e e-mail válidos e execute novamente.')
        chosen = getpass.getpass('Crie uma senha com pelo menos 12 caracteres (não aparece ao digitar): ')
        if len(chosen) < 12 or chosen != getpass.getpass('Repita a senha: '):
            raise RuntimeError('As senhas devem ser iguais e ter pelo menos 12 caracteres. Execute novamente.')
        code = common + '''
import json,secrets,time,sys
fields=json.load(sys.stdin)
with database(app) as db:
 db.execute('BEGIN IMMEDIATE')
 if db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]:
  raise RuntimeError('Administrador já criado por outro processo.')
 db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',(secrets.token_hex(12),email(fields['email']),text(fields['name'],120),password(fields['password']),'admin',time.time()))
print(json.dumps({'ok':True}))
'''
        backend(code, {'name':name,'email':address,'password':chosen})
        del chosen
        print('Seu acesso foi criado. Use o e-mail informado e a senha escolhida.')
    else:
        print('Já existe um administrador. Entre com o acesso criado anteriormente.')
    values = dict(line.split('=', 1) for line in config.read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.lstrip().startswith('#'))
    url = values.get('APP_URL', 'http://127.0.0.1:3000').strip()
    print('\nEndereço configurado: ' + url)
    print('Para que outras pessoas acessem e para receber WhatsApp real, falta configurar HTTPS/domínio e Meta.')
    print('O roteiro está em deploy/INSTALAR-WINDOWS.md. Não abra a porta 3000 na internet.')
    print('Mantenha esta janela aberta durante o teste. Fechar a janela encerra a aplicação.\n')
    with socket.socket() as sock:
        occupied = sock.connect_ex(('127.0.0.1', 3000)) == 0
    if occupied:
        print('A porta 3000 já está em uso. Não vou iniciar outro servidor. Confira o processo com TI.')
        return
    # The browser opens after the server has had time to bind. A launch failure remains in this console.
    timer = threading.Timer(3, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()
    run([PYTHON, ROOT / 'launch.py', '--config', config, 'serve'])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nAplicação encerrada.')
    except subprocess.CalledProcessError as error:
        # Never print subprocess input, stdout, stderr or exception repr: they may contain private data.
        print(f'\nUma etapa falhou (código {error.returncode}). Verifique Python, internet e configuração com TI.')
        sys.exit(1)
    except Exception as error:
        print('\n' + str(error))
        sys.exit(1)
