"""Pilot ngrok runner: only port 3002 gateway is published, never CRM port 3000."""
from collections import deque
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request

from waitress import create_server
from configure_connections import read_config,save_config
from webhook_gateway import create_gateway,probe_backend
from public_webhook_check import verify_public

ROOT=Path(__file__).resolve().parent


def find_ngrok():
    for path in (ROOT/'ngrok.exe',ROOT/'tools/ngrok.exe'):
        if path.is_file():return str(path)
    path=shutil.which('ngrok')
    if path:return path
    raise ValueError('Não encontrei ngrok.exe. Baixe o agente oficial para Windows e copie ngrok.exe para esta pasta do CRM.')


def tunnel_url(sender=urllib.request.urlopen):
    with sender('http://127.0.0.1:4040/api/tunnels',timeout=2) as response:
        data=json.load(response)
    for tunnel in data.get('tunnels',[]):
        target=str(tunnel.get('config',{}).get('addr',''))
        target=target if '://' in target else 'http://'+target
        parsed=urllib.parse.urlsplit(target)
        public=tunnel.get('public_url','')
        if parsed.hostname in ('127.0.0.1','localhost') and parsed.port==3002 and public.startswith('https://'):
            return public
    return None


def main():
    values=read_config(ROOT/'.env')
    if not values.get('NGROK_AUTHTOKEN'):
        raise ValueError('Execute CONFIGURAR-META-E-HTTPS.cmd antes de iniciar o túnel.')
    exe=find_ngrok()
    print('Conferindo a aplicação e os segredos carregados no CRM...',flush=True)
    probe_backend(values)
    server=create_server(create_gateway(values),host='127.0.0.1',port=3002,threads=4,max_request_body_size=1_000_000)
    worker=threading.Thread(target=server.run,daemon=True)
    worker.start()
    process=None
    logs=deque(maxlen=5)
    try:
        env={**os.environ,'NGROK_AUTHTOKEN':values['NGROK_AUTHTOKEN']}
        process=subprocess.Popen([exe,'http','http://127.0.0.1:3002','--inspect=false','--log=stdout','--log-format=json'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        def drain():
            for line in process.stdout:
                codes=re.findall(r'ERR_NGROK_\d+',line)
                if codes:logs.extend(codes)
        threading.Thread(target=drain,daemon=True).start()
        print('Abrindo o túnel HTTPS de teste. Nenhuma tela do CRM será publicada...',flush=True)
        public=None
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if process.poll() is not None:break
            try:public=tunnel_url()
            except (OSError,ValueError):pass
            if public:break
            time.sleep(.5)
        if not public:
            codes=', '.join(sorted(set(logs)))
            raise ValueError('O agente ngrok não abriu o túnel. Confira conta, authtoken e internet.'+(' Código: '+codes if codes else ''))
        print('Conferindo o desafio público e o isolamento das rotas...',flush=True)
        callback=verify_public(public,values['META_VERIFY_TOKEN'])
        # Preserve LAN URL and every credential; only store the callback separately.
        latest=read_config(ROOT/'.env')
        save_config({**latest,'META_WEBHOOK_URL':callback},ROOT/'.env')
        local=ROOT/'META-CONFIGURACAO-LOCAL.txt'
        local.write_text('USO LOCAL. NÃO ENVIAR NO CHAT.\n\nURL de callback:\n'+callback+'\n\nVerificar token (token de verificação, não o token de acesso):\n'+values['META_VERIFY_TOKEN']+'\n\nCadastre esses dois valores na Meta, clique Verificar e salvar e ative Assinar webhooks para Sais Blue - Willian.\n',encoding='utf-8')
        print('\nURL PÚBLICA VALIDADA: '+callback)
        print('Abra META-CONFIGURACAO-LOCAL.txt e copie os valores para a Meta. Não envie o arquivo ou token no chat.')
        print('O desafio HTTPS funcionou e as rotas /, /login e /api/contacts responderam 404 neste túnel.')
        print('Mantenha esta janela e a janela do CRM abertas durante o teste. Fechar esta janela encerra o túnel.')
        print('Isso ainda não comprova entrega real de mensagens nem publicação do app na Meta.\n',flush=True)
        while process.poll() is None:time.sleep(1)
        print('O túnel foi encerrado pelo agente. Reinicie a conexão antes de testar mensagens.')
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        server.close()


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nConexão HTTPS encerrada.')
    except ValueError as error:print('\n'+str(error))
    except OSError:print('\nNão foi possível abrir a conexão. Confira se a porta 3002 já está ocupada ou se há bloqueio de rede.')
    except Exception:print('\nA conexão não foi concluída. Nenhum segredo foi exibido; confira os passos do roteiro.')
