"""Read-only Graph API diagnosis of Sais Blue's official phone; never sends/registers."""
import getpass
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

PHONE_ID = '321395016679053'
ACCOUNT_ID = '1398958113869625'
OFFICIAL_NUMBER = '555434436405'
VERSION = 'v25.0'


def graph(path, fields, token, sender=urllib.request.urlopen):
    if not re.fullmatch(r'[0-9]+(?:/phone_numbers|/subscribed_apps)?', path):
        raise ValueError('Caminho inválido.')
    url = f'https://graph.facebook.com/{VERSION}/{path}'
    if fields:
        url += '?fields=' + fields
    request = urllib.request.Request(url, headers={'Authorization':'Bearer '+token})
    try:
        with sender(request, timeout=20) as response:
            return {'ok':True,'data':json.load(response)}
    except urllib.error.HTTPError as error:
        try:
            details=json.load(error).get('error',{})
        except (ValueError,TypeError):
            details={}
        # Only structured codes, never raw headers/body or an exception containing credentials.
        return {'ok':False,'http_status':error.code,'code':details.get('code'),'subcode':details.get('error_subcode')}
    except (OSError,ValueError,TypeError):
        return {'ok':False,'network_error':True}


def diagnose(token, sender=urllib.request.urlopen):
    report={'official_phone_id':PHONE_ID,'official_account_reference':ACCOUNT_ID,'target_number':OFFICIAL_NUMBER,
            'read_access':'unknown','whatsapp_activated':False,'findings':[]}
    phone=graph(PHONE_ID,'display_phone_number,verified_name',token,sender)
    if not phone['ok']:
        report['phone_check']=phone
        if phone.get('code')==190:
            report['findings'].append('TOKEN_INVALIDO: gerar token novo autorizado para Sais Blue - Willian, não apenas Test Messaging Account.')
        elif phone.get('network_error'):
            report['findings'].append('SEM_RESPOSTA_META: verificar internet/proxy do computador. Nenhuma alteração foi feita.')
        else:
            report['findings'].append('SEM_ACESSO_CONFIRMADO: revisar autorização do app/usuário para o número oficial; o ID de perfil, sozinho, não garante acesso pela API.')
        return report
    data=phone['data']
    actual=re.sub(r'\D','',data.get('display_phone_number',''))
    if actual!=OFFICIAL_NUMBER:
        report['findings'].append('NUMERO_DIVERGENTE: a consulta não retornou o número oficial esperado. Não prosseguir com ativação.')
        return report
    report['read_access']='confirmed'
    report['display_phone_number']=data['display_phone_number']
    report['findings'].append('ACESSO_DE_LEITURA_OK: o token consegue consultar o número oficial. Isso ainda não confirma envio/recebimento.')
    # Probe optional fields separately. An unsupported field is unknown, never interpreted as false.
    for field in ('platform_type','is_on_biz_app','code_verification_status'):
        result=graph(PHONE_ID,field,token,sender)
        report[field]=result['data'].get(field,'unknown') if result['ok'] else 'unknown'
    account=graph(ACCOUNT_ID+'/phone_numbers','id,display_phone_number',token,sender)
    report['account_phone_list_access']=account['ok']
    if account['ok']:
        report['phone_belongs_to_account']=any(str(p.get('id'))==PHONE_ID for p in account['data'].get('data',[]))
        if report['phone_belongs_to_account']:
            subscriptions=graph(ACCOUNT_ID+'/subscribed_apps','',token,sender)
            report['app_subscription_query_ok']=subscriptions['ok']
            if subscriptions['ok']:
                report['subscribed_app_ids']=[str(p.get('whatsapp_business_api_data',{}).get('id','')) for p in subscriptions['data'].get('data',[])]
    if report.get('platform_type')!='CLOUD_API':
        report['findings'].append('HABILITACAO_A_CONFIRMAR: a resposta não confirmou plataforma CLOUD_API. Verificar onboarding/coexistência antes de registrar, migrar ou enviar pelo número.')
    else:
        report['findings'].append('PLATAFORMA_CLOUD_API_IDENTIFICADA: ainda é necessário validar cadastro, permissões e webhook público com uma mensagem real.')
    report['findings'].append('SEM_MUTACOES: nenhuma mensagem enviada, conta criada, número registrado ou migração executada.')
    return report


def main():
    print('SAIS BLUE — diagnóstico do número OFICIAL +55 54 3443-6405')
    print('Somente consultas. Não usa o número de teste e não altera o aplicativo do celular.')
    print('Use token válido com acesso a Sais Blue - Willian. Não envie o token no chat.')
    token=getpass.getpass('Cole o token da Meta (não aparece ao digitar) e pressione Enter: ').strip()
    if not token:
        print('Sem token: nenhuma consulta executada.');return
    report=diagnose(token)
    del token
    output=Path(__file__).resolve().parent/'DIAGNOSTICO-WHATSAPP-RESULTADO.txt'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n'+output.read_text(encoding='utf-8'))
    print('\nResumo salvo em DIAGNOSTICO-WHATSAPP-RESULTADO.txt. Pode compartilhar esse resumo; ele não contém token.')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nConsulta cancelada.')
    except Exception:print('Não foi possível concluir o diagnóstico. Nenhuma alteração na conta foi feita.')
