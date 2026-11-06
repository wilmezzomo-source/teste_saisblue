"""Local read-only go-live checklist for the Windows CRM installation."""
import json
from pathlib import Path
import sqlite3
from sqlite_context import connection
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent


def check(root=ROOT, sender=urllib.request.urlopen):
    from update_windows import settings
    rows=[]
    config=root/'.env'
    if not config.is_file():
        return ['FALHA: execute este validador na pasta ORIGINAL do CRM; .env ausente.']
    values=settings(config)
    url=values.get('APP_URL','').rstrip('/')
    if not url or urlsplit(url).scheme not in ('http','https'):
        return ['FALHA: APP_URL inválida; revisar configuração local.']
    rows.append('ENDERECO_DA_EQUIPE: '+url)
    missing=[p for p in ['public/index.html','public/brand/sb-logo.png','public/data/cities.json','public/vendor/leaflet/leaflet.js'] if not (root/p).is_file()]
    rows.append('ARQUIVOS: '+('OK' if not missing else 'FALHA — atualização incompleta; faltam '+', '.join(missing)))
    database=Path(values.get('CRM_DB') or root/'data/crm.sqlite3')
    if not database.is_absolute():database=root/database
    if not database.is_file():
        rows.append('BANCO: FALHA — banco configurado não encontrado; não criei outro.')
    else:
        try:
            with connection(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=3) as db:
                active=db.execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0]
                contacts=db.execute('SELECT COUNT(*) FROM contacts').fetchone()[0]
                rows.append(f'BANCO: OK — {active} usuário(s) ativo(s), {contacts} contato(s).')
        except sqlite3.Error:
            rows.append('BANCO: FALHA — leitura não confirmada; verifique acesso e inicialização do CRM.')
    try:
        with sender(url+'/healthz',timeout=5) as response:
            health=json.load(response)
            ok=health.get('ok') is True
            rows.append('VERSAO: '+health.get('version','anterior — atualizar o código'))
        rows.append('APLICACAO: '+('OK — respondeu no endereço configurado.' if ok else 'FALHA — resposta inesperada.'))
    except (OSError,ValueError):
        rows.append('APLICACAO: FALHA — abra INICIAR-NO-WINDOWS.cmd e mantenha a janela aberta.')
    try:
        with sender(url+'/api/contacts',timeout=5):
            rows.append('LOGIN: FALHA — endpoint de contatos respondeu sem exigir login.')
    except urllib.error.HTTPError as error:
        rows.append('LOGIN: '+('OK — dados exigem autenticação.' if error.code==401 else 'INCONCLUSIVO — resposta HTTP '+str(error.code)))
    except OSError:
        rows.append('LOGIN: INCONCLUSIVO — aplicação inacessível.')
    rows.append('TESTE_OBRIGATORIO: em OUTRO computador da mesma rede, abrir '+url+', entrar e editar um card.')
    rows.append('WHATSAPP: não validado por este teste. Executar DIAGNOSTICAR-WHATSAPP.cmd para consultar o número oficial.')
    if urlsplit(url).scheme=='http':
        rows.append('HTTPS: pendente. Endereço HTTP serve ao piloto LAN; não publicar a porta 3000 na internet.')
    return rows


if __name__=='__main__':
    try:
        output='\n'.join(check())
        (ROOT/'VALIDACAO-INSTALACAO-RESULTADO.txt').write_text(output,encoding='utf-8')
        print(output)
    except Exception:
        print('Falha ao validar a instalação. Nenhuma configuração foi modificada.')
