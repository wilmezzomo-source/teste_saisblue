"""Configure the installed Windows CRM without exposing credentials in chat or argv."""
import ctypes
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / '.env'
EXPECTED_PHONE = '555434436405'


def read_config(path=CONFIG):
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator:
            raise ValueError('Configuração inválida. Não alterei o arquivo.')
        result[key.strip()] = value.strip()
    return result


def save_config(values, path=CONFIG):
    # Preserve every existing key, especially CRM_DB and the Meta credentials.
    if any('\n' in str(v) or '\r' in str(v) for v in values.values()):
        raise ValueError('Configuração inválida.')
    descriptor, temporary = tempfile.mkstemp(prefix='.crm-config-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as target:
            target.write(''.join(f'{k}={v}\n' for k,v in values.items()))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_ip(value):
    address = ipaddress.IPv4Address(value)
    if not any(address in ipaddress.IPv4Network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('Use o IPv4 privado da rede da empresa, não um IP público ou 127.0.0.1.')
    return str(address)


def lan_values(values, address):
    address = private_ip(address)
    if values.get('APP_ENV') == 'production':
        raise ValueError('Esta instalação já usa produção/HTTPS. Não vou substituir por HTTP; use o endereço HTTPS existente.')
    return {**values, 'APP_ENV':'lan', 'APP_URL':f'http://{address}:3000', 'CRM_LISTEN_HOST':address, 'ALLOW_SIMULATION':'0'}


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell(command):
    return subprocess.run(['powershell.exe','-NoProfile','-Command',command], cwd=ROOT,
                          capture_output=True, text=True, check=True)


def network_addresses():
    command = "Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress,InterfaceAlias | ConvertTo-Json -Compress"
    result = json.loads(powershell(command).stdout or '[]')
    if isinstance(result, dict):
        result = [result]
    usable = []
    for item in result:
        try:
            usable.append((private_ip(item['IPAddress']), item['InterfaceAlias']))
        except ValueError:
            continue
    return usable


def configure_lan():
    values = read_config()
    if values.get('APP_ENV') == 'production':
        raise ValueError('A instalação já está em modo HTTPS. Use APP_URL para acesso e verifique DNS/firewall com TI.')
    print('\nAcesso pela rede interna: HTTP, sem criptografia. É uma etapa de validação local.')
    print('Para uso externo e WhatsApp real, precisamos concluir HTTPS/domínio. Não encaminhe a porta 3000 no roteador.')
    addresses = network_addresses()
    if not addresses:
        raise ValueError('Não encontrei um IPv4 privado. Verifique a conexão de rede do servidor.')
    for index, (address, interface) in enumerate(addresses, 1):
        print(f'{index}. {address} — {interface}')
    selected = int(input('Digite o número da placa conectada à rede dos outros computadores: '))
    if not 1 <= selected <= len(addresses):
        raise ValueError('Opção inválida.')
    address = addresses[selected - 1][0]
    updated = lan_values(values, address)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('Feche e abra ATIVAR-REDE-E-WHATSAPP.cmd com botão direito > Executar como administrador. O Windows exige isso para a regra de firewall.')
    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not python.exists():
        raise ValueError('Não encontrei o Python da instalação. Execute este assistente na mesma pasta do CRM que já funciona.')
    # Narrow, named rule; no global firewall disable, no router changes, no public profile.
    command = (
        "$ErrorActionPreference='Stop'; "
        "Get-NetFirewallRule -DisplayName 'SaisBlue CRM - LAN' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
        f"New-NetFirewallRule -DisplayName 'SaisBlue CRM - LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3000 -LocalAddress {address} -RemoteAddress LocalSubnet -Profile Private,Domain -Program {ps_literal(python)} | Out-Null"
    )
    powershell(command)
    save_config(updated)
    profiles = powershell('Get-NetConnectionProfile | Select-Object InterfaceAlias,NetworkCategory | ConvertTo-Json -Compress').stdout.strip()
    print('\nConfiguração salva. Reinicie o CRM (Ctrl+C no terminal antigo e abra INICIAR-NO-WINDOWS.cmd).')
    print('Depois, use este endereço no servidor e nos outros computadores da mesma rede: ' + updated['APP_URL'])
    print('Entre novamente e gere novos convites em Equipe usando esse endereço.')
    print('Se a rede estiver classificada como Public, a regra não libera o acesso. Peça à TI para validar o perfil; não alterei o perfil da rede.')
    print('Perfis de rede encontrados: ' + profiles)
    print('Peça à TI uma reserva de IP no DHCP para o endereço não mudar.')


def meta_url(version, number_id):
    if not re.fullmatch(r'v\d+\.\d+', version) or not re.fullmatch(r'\d+', number_id):
        raise ValueError('Informe a versão da API e o Phone Number ID da Meta, não o telefone.')
    return f'https://graph.facebook.com/{version}/{number_id}?fields=display_phone_number,verified_name'


def verify_meta(number_id, token, version, sender=urllib.request.urlopen):
    req = urllib.request.Request(meta_url(version,number_id), headers={'Authorization':'Bearer ' + token})
    try:
        with sender(req, timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(f'A Meta não autorizou a consulta (HTTP {error.code}). Confira token, permissões e Phone Number ID. Não salvei as credenciais.') from None
    except (OSError, ValueError):
        raise ValueError('Não consegui confirmar as credenciais na Meta. Confira internet, conta e API. Não salvei as credenciais.') from None
    actual = re.sub(r'\D','',result.get('display_phone_number',''))
    if actual != EXPECTED_PHONE:
        raise ValueError('O número retornado pela Meta não é +55 54 3443-6405. Não salvei as credenciais para evitar conectar outra conta.')
    return result


def configure_meta():
    values = read_config()
    print('\nEsta etapa exige acesso ao app da empresa em developers.facebook.com e ao WhatsApp Business Platform.')
    print('Só o número do celular não permite a conexão. Não desconecte o aplicativo atual para tentar este assistente.')
    number_id = input('Phone Number ID (ID fornecido pela Meta, não o telefone): ').strip()
    token = getpass.getpass('Token de acesso da Meta (fica oculto ao digitar): ').strip()
    secret = getpass.getpass('App Secret do app Meta (fica oculto ao digitar): ').strip()
    if not token or not secret:
        raise ValueError('Informe as credenciais oficiais da Meta. Nada foi alterado.')
    version = values.get('META_API_VERSION','v22.0')
    result = verify_meta(number_id,token,version)
    verification = values.get('META_VERIFY_TOKEN') or secrets.token_urlsafe(32)
    updated = {**values,'META_PHONE_NUMBER_ID':number_id,'META_ACCESS_TOKEN':token,'META_APP_SECRET':secret,'META_VERIFY_TOKEN':verification,'ALLOW_SIMULATION':'0'}
    save_config(updated)
    print('\nA Meta confirmou o acesso ao número ' + result['display_phone_number'] + '.')
    print('Isso valida o token e o número. Ainda precisamos validar a assinatura com um evento real e assinar o webhook.')
    url = values.get('APP_URL','')
    if urlsplit(url).scheme != 'https':
        print('Falta publicar HTTPS. O endereço da rede interna não pode receber os eventos da Meta pela internet.')
        callback = 'PENDENTE — configurar URL pública HTTPS antes de cadastrar na Meta.'
    else:
        callback = url.rstrip('/') + '/webhooks/whatsapp'
        print('URL para cadastrar após confirmar HTTPS público: ' + callback)
    setup = ROOT / 'META-CONFIGURACAO-LOCAL.txt'
    setup.write_text('USO LOCAL. NÃO ENVIAR NO CHAT OU PUBLICAR.\nWebhook: '+callback+'\nToken de verificação: '+verification+'\nAssine os eventos messages da conta WhatsApp.\n', encoding='utf-8')
    print('Os dados de verificação estão em META-CONFIGURACAO-LOCAL.txt, nesta pasta. Não envie esse arquivo aqui.')
    print('Reinicie o CRM após concluir a configuração. Uma pessoa deve mandar mensagem para o número e testar a resposta pelo CRM.')


def diagnose():
    values = read_config()
    print('\nRESUMO SEM SENHAS OU TOKENS')
    print('Modo: ' + values.get('APP_ENV','não definido'))
    print('Endereço: ' + values.get('APP_URL','não definido'))
    print('Interface: ' + values.get('CRM_LISTEN_HOST','127.0.0.1'))
    for address, interface in network_addresses():
        print('Rede: '+address+' — '+interface)
    print('Credenciais Meta preenchidas: ' + ('sim' if all(values.get(k) for k in ['META_PHONE_NUMBER_ID','META_ACCESS_TOKEN','META_APP_SECRET','META_VERIFY_TOKEN']) else 'não'))
    print('Preenchimento não confirma webhook ou conexão real.')


def main():
    if sys.platform != 'win32':
        raise ValueError('Execute este assistente no Windows do servidor.')
    if not CONFIG.exists():
        raise ValueError('Não encontrei .env. Copie os arquivos da atualização para a pasta original do CRM, preservando .env, .venv e data.')
    print('SAIS BLUE CRM — acesso da equipe e conexão Meta')
    print('1. Configurar acesso na mesma rede da empresa\n2. Configurar e verificar credenciais do WhatsApp oficial\n3. Mostrar diagnóstico sem senhas/tokens')
    choice = input('Escolha a etapa: ').strip()
    if choice == '1':
        configure_lan()
    elif choice == '2':
        configure_meta()
    elif choice == '3':
        diagnose()
    else:
        raise ValueError('Opção inválida.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not print command bodies or HTTP responses: they may contain credentials.
        print('\n' + ('O Windows recusou a operação. Verifique privilégios e rede com TI.' if isinstance(error, subprocess.CalledProcessError) else str(error)))
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nEtapa cancelada.')
