"""Setup the real phone credentials locally; all remote calls are read-only."""
import getpass
from pathlib import Path
import re
import secrets
from configure_connections import read_config,save_config
from diagnostico_whatsapp import graph,PHONE_ID,OFFICIAL_NUMBER,VERSION

ROOT=Path(__file__).resolve().parent
APP_ID='1111043088389561'


def prepare(values,token,secret,ngrok_token,sender=None):
    kwargs={'sender':sender} if sender else {}
    phone=graph(PHONE_ID,'display_phone_number,verified_name',token,**kwargs)
    if not phone['ok']:
        raise ValueError(f"A Meta não autorizou a consulta ao número oficial. HTTP {phone.get('http_status','?')}, código {phone.get('code','?')}, subcódigo {phone.get('subcode','?')}. Gere um token com acesso a Sais Blue - Willian após a inscrição do número.")
    if re.sub(r'\D','',phone['data'].get('display_phone_number',''))!=OFFICIAL_NUMBER:
        raise ValueError('O número retornado não corresponde ao Willian. Nada foi salvo.')
    app=graph(APP_ID,'id,name',APP_ID+'|'+secret,**kwargs)
    if not app['ok'] or str(app['data'].get('id'))!=APP_ID:
        raise ValueError('A Meta não confirmou a chave secreta do app Sais Blue CRM. Confira Configurações do app > Básico > Chave secreta.')
    if not ngrok_token:
        raise ValueError('Informe o authtoken da sua conta ngrok para o túnel de teste.')
    return {**values,'META_PHONE_NUMBER_ID':PHONE_ID,'META_ACCESS_TOKEN':token,'META_APP_SECRET':secret,
            'META_VERIFY_TOKEN':values.get('META_VERIFY_TOKEN') or secrets.token_urlsafe(32),
            'META_API_VERSION':VERSION,'NGROK_AUTHTOKEN':ngrok_token,'ALLOW_SIMULATION':'0'}


def main():
    config=ROOT/'.env'
    if not config.exists():
        raise ValueError('Execute na pasta ORIGINAL do CRM já instalado, onde está .env.')
    values=read_config(config)
    print('SAIS BLUE — configurar o número oficial e o túnel HTTPS de teste\n')
    print('As credenciais são digitadas sem aparecer e ficam somente no servidor. Não envie capturas desta configuração.')
    print('Enter mantém um valor já configurado. App Secret, token Meta e authtoken ngrok são três dados diferentes.')
    token=getpass.getpass('Token da META autorizado para Sais Blue - Willian: ').strip() or values.get('META_ACCESS_TOKEN','')
    secret=getpass.getpass('CHAVE SECRETA do app Sais Blue CRM (Configurações > Básico): ').strip() or values.get('META_APP_SECRET','')
    ngrok=getpass.getpass('AUTHTOKEN da conta NGROK: ').strip() or values.get('NGROK_AUTHTOKEN','')
    if not token or not secret:
        raise ValueError('Token Meta e App Secret são obrigatórios. Nada foi salvo.')
    updated=prepare(values,token,secret,ngrok)
    save_config(updated,config)
    print('\nCredenciais conferidas pela Meta e salvas no servidor. Isso ainda não confirma entrega de mensagens.')
    print('Agora pare o CRM com Ctrl+C e abra INICIAR-NO-WINDOWS.cmd para carregar a configuração.')
    print('Depois execute INICIAR-CONEXAO-HTTPS.cmd e mantenha as duas janelas abertas durante o teste.')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nCancelado. A configuração só é salva após as verificações.')
    except ValueError as error:print('\n'+str(error))
    except Exception:print('\nA configuração não foi concluída. Confira a instalação. Não envie credenciais no chat.')
