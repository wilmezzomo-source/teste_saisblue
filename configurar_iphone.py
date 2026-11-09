"""Prepare the iPhone app and the Windows HTTPS gateway without changing Meta or LAN."""
import argparse
import ctypes
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit
import zipfile

from configure_connections import read_config, save_config, private_ip, ps_literal

ROOT = Path(__file__).resolve().parent
PUBLIC_URL = 'https://crm.saisblue.com.br'
CADDY_URL = 'https://github.com/caddyserver/caddy/releases/download/v2.11.9/caddy_2.11.9_windows_amd64.zip'
CADDY_SHA512 = '98753d5d42650383d00619ac70917a217141f9e92314185bf6c1b8b439cfcfdf8393da0ebb4675c8cb3b23d29a19aabe99dc5aca64fa1bfc3a1ba22509b06871'


def layout(root=ROOT):
    root = Path(root).resolve()
    values = read_config(root/'.env')
    address = values.get('CRM_LISTEN_HOST','127.0.0.1')
    if address!='127.0.0.1':
        address = private_ip(address)
    url = values.get('CRM_PUBLIC_URL',PUBLIC_URL).rstrip('/')
    parsed = urlsplit(url)
    if url != PUBLIC_URL:
        raise ValueError('Esta configuração foi preparada para crm.saisblue.com.br. Peça revisão antes de usar outro domínio.')
    directory = root/'data'/'external'
    return root, values, address, parsed.hostname, directory


def caddy_config(root, address, domain):
    directory = Path(root)/'data'/'external'
    quote = lambda p: json.dumps(str(p).replace('\\','/'))
    return f'''{{
    email willian@saisblue.com.br
    admin 127.0.0.1:2019
    storage file_system {{
        root {quote(directory/'certificates')}
    }}
    log {{
        output file {quote(directory/'caddy.log')} {{
            roll_size 10MiB
            roll_keep 3
        }}
    }}
}}
{domain} {{
    reverse_proxy {address}:3000
}}
'''


def public_outbound_ip():
    try:
        with urllib.request.urlopen('https://api.ipify.org',timeout=5) as response:
            address = ipaddress.IPv4Address(response.read(64).decode().strip())
        return str(address) if address.is_global else None
    except Exception:
        return None


def request_text(address, outbound=None):
    observed = f'IP de saída observado: {outbound}. TI/provedor precisa confirmar se é público, fixo e alcançável.' if outbound else 'IP público da empresa: PENDENTE. Solicitar à TI/provedor de internet.'
    return f'''SAIS BLUE CRM — SOLICITAÇÃO DE ACESSO EXTERNO

Para a TELIUM (DNS do domínio saisblue.com.br):
Criar um registro A para crm.saisblue.com.br apontando ao IPv4 público da conexão da empresa, confirmado pela TI/provedor.
{observed}
Não criar AAAA sem conectividade IPv6 validada. Não alterar o site, os servidores de nomes, registros MX ou e-mails existentes.
O CRM roda no servidor da empresa; esta solicitação não pressupõe que a hospedagem do site execute o CRM.

Para a TI/PROVEDOR que cuida da rede da empresa:
1. Confirmar IP público alcançável, preferencialmente fixo; confirmar ausência de CGNAT. Se houver CGNAT, solicitar uma conexão pública ou apresentar alternativa de hospedagem, com custo para aprovação.
2. Reservar o IP interno {address} para o servidor Windows no roteador/DHCP.
3. Encaminhar SOMENTE TCP 80 e TCP 443 do roteador para {address}, portas 80 e 443. Não encaminhar 3000, 3002, 2019 ou área de trabalho remota.
4. Verificar se as portas 80/443 já atendem outro serviço antes de alterar o roteador. O assistente não encerra serviços existentes.
5. Se necessário, configurar DNS interno crm.saisblue.com.br → {address} para uso na rede da empresa sem depender de NAT de retorno.
6. No servidor, após o DNS e o roteador estarem prontos: Sais Blue CRM → Configurar iPhone → opção 2. O Windows pedirá autorização local de administrador para criar uma regra de firewall e uma tarefa de HTTPS próprias deste CRM.

VALIDAÇÃO EM 4G/5G:
Abrir https://crm.saisblue.com.br no iPhone com Wi-Fi desligado. Deve aparecer o login, com certificado válido e sem aviso de segurança. Entrar com a conta da atendente e verificar que ela vê apenas seus cards.
No Safari: Compartilhar → Adicionar à Tela de Início → Adicionar. Abrir pelo ícone Sais Blue CRM. Em Avisos, ativar as notificações deste aparelho e aceitar a permissão do iOS. Requer iOS 16.4 ou superior.
Tocar em Testar em 10 segundos e bloquear o iPhone. Validar a chegada do aviso. Ajustes de Foco/Notificações do iPhone podem silenciar o som.

O servidor e o CRM precisam permanecer ligados e com internet. A tarefa de HTTPS inicia com o Windows; o CRM continua sendo iniciado pelo aplicativo Sais Blue CRM.
A conexão Meta/ngrok de mensagens atual é preservada. Não trocar o callback existente nesta etapa.
Este arquivo não contém senhas, tokens ou chave privada.
'''


def prepare(root=ROOT, detect_ip=True):
    root, values, address, domain, directory = layout(root)
    if address=='127.0.0.1':
        raise ValueError('Configure primeiro o acesso da rede da empresa pelo assistente de rede do CRM.')
    directory.mkdir(parents=True,exist_ok=True)
    values['CRM_PUBLIC_URL'] = PUBLIC_URL
    values.setdefault('PUSH_SUBJECT','mailto:willian@saisblue.com.br')
    save_config(values,root/'.env')
    # This local key never goes in the public repository or the Telium request.
    db = Path(values.get('CRM_DB') or root/'data'/'crm.sqlite3')
    if not db.is_absolute():
        db = root/db
    from web_push import public_key
    from types import SimpleNamespace
    keyfile = Path(values.get('PUSH_KEY_FILE') or db.resolve().parent/'webpush-private.pem')
    if not keyfile.is_absolute():
        keyfile = root/keyfile
    public_key(SimpleNamespace(config={'PUSH_KEY_FILE':str(keyfile)}),create=True)
    (directory/'Caddyfile').write_text(caddy_config(root,address,domain),encoding='utf-8')
    request = root/'SOLICITACAO-TELIUM.txt'
    request.write_text(request_text(address,public_outbound_ip() if detect_ip else None),encoding='utf-8-sig')
    print('App e chave de notificações preparados. Nenhuma credencial foi exibida.')
    print('Abra SOLICITACAO-TELIUM.txt e encaminhe o conteúdo à Telium e a quem cuida da rede.')
    print('O acesso externo depende do DNS, do IP público e do roteador descritos nesse arquivo.')
    if os.name=='nt':
        os.startfile(request)
    return request


def install_caddy(root=ROOT, opener=urllib.request.urlopen):
    target = Path(root)/'tools'/'caddy.exe'
    # Download and check the pinned official release, including on subsequent activations.
    with opener(CADDY_URL,timeout=60) as response:
        archive = response.read(65_000_001)
    if len(archive)>65_000_000 or hashlib.sha512(archive).hexdigest()!=CADDY_SHA512:
        raise ValueError('O download HTTPS não passou na verificação. Nada foi executado.')
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        entry = package.getinfo('caddy.exe')
        if entry.file_size>100_000_000:
            raise ValueError('Pacote HTTPS inválido.')
        binary = package.read(entry)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Windows cannot replace a running image. An identical pinned binary needs no write.
    if not target.exists() or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(binary).digest():
        temporary = target.with_suffix('.download')
        temporary.write_bytes(binary)
        os.replace(temporary,target)
    return target


def task_script(root, executable, config):
    suffix = hashlib.sha256(str(Path(root).resolve()).lower().encode()).hexdigest()[:12]
    task = 'SaisBlueCRM-HTTPS-'+suffix
    rule = 'SaisBlueCRM-HTTPS-'+suffix
    args = subprocess.list2cmdline(['run','--config',str(config),'--adapter','caddyfile'])
    exe, arg = ps_literal(executable), ps_literal(args)
    return f'''$ErrorActionPreference='Stop'
$exe={exe}
$crmArguments={arg}
$name={ps_literal(task)}
$existing=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($existing -and (@($existing.Actions).Count -ne 1 -or $existing.Actions[0].Execute -ne $exe -or $existing.Actions[0].Arguments -ne $crmArguments)) {{throw 'Já existe uma tarefa diferente com este nome. Peça revisão à TI.'}}
$listeners=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {{$_.LocalPort -in 80,443}}
foreach ($listener in $listeners) {{
    $process=Get-Process -Id $listener.OwningProcess -ErrorAction Stop
    if ($process.Path -ne $exe) {{throw 'Porta 80 ou 443 usada por outro serviço. Não encerrei nenhum processo.'}}
}}
$action=New-ScheduledTaskAction -Execute $exe -Argument $crmArguments -WorkingDirectory {ps_literal(root)}
$trigger=New-ScheduledTaskTrigger -AtStartup
$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Get-NetFirewallRule -Name {ps_literal(rule)} -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name {ps_literal(rule)} -DisplayName 'Sais Blue CRM HTTPS' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80,443 -Program $exe -Profile Any | Out-Null
Start-ScheduledTask -TaskName $name
'''


def activate(root=ROOT):
    if os.name!='nt':
        raise ValueError('A ativação deste assistente deve ser feita no servidor Windows.')
    if not ctypes.windll.shell32.IsUserAnAdmin():
        args = subprocess.list2cmdline([str(Path(__file__).resolve()),'--action','activate'])
        result = ctypes.windll.shell32.ShellExecuteW(None,'runas',sys.executable,args,str(root),1)
        if result<=32:
            raise ValueError('O Windows não autorizou a configuração do HTTPS.')
        return
    root, values, address, domain, directory = layout(root)
    config = directory/'Caddyfile'
    if not config.is_file():
        raise ValueError('Execute primeiro a opção 1 para preparar o app e a solicitação de rede.')
    socket.getaddrinfo(domain,443,type=socket.SOCK_STREAM)
    print('Baixando e conferindo o servidor HTTPS oficial…')
    executable = install_caddy(root)
    subprocess.run([str(executable),'validate','--config',str(config),'--adapter','caddyfile'],check=True,cwd=root)
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',task_script(root,executable,config)],check=True,cwd=root)
    print('HTTPS iniciado e configurado para iniciar com o Windows. A emissão do certificado depende de DNS e portas 80/443 alcançáveis.')
    print('Abra o app Sais Blue CRM → Iniciar / reconectar. Depois valide o endereço no iPhone em 4G/5G.')
    print('Se não abrir, execute a opção 3. Não altere a conexão Meta/ngrok atual.')


def diagnose(root=ROOT, opener=urllib.request.urlopen):
    root, values, address, domain, directory = layout(root)
    report = ['SAIS BLUE CRM — DIAGNÓSTICO DO ACESSO EXTERNO','Este relatório não contém credenciais.']
    try:
        ips = sorted({r[4][0] for r in socket.getaddrinfo(domain,443,type=socket.SOCK_STREAM)})
        report.append('DNS: '+', '.join(ips))
    except OSError:
        report.append('DNS: endereço ainda não encontrado. A Telium precisa criar o registro.')
    for label,url in [('CRM no servidor',f'http://{address}:3000/healthz'),('HTTPS do app',PUBLIC_URL+'/healthz')]:
        try:
            with opener(url,timeout=10) as response:
                body = json.loads(response.read(1024))
            report.append(label+': respondeu; versão '+str(body.get('version','desconhecida')))
        except Exception as exc:
            report.append(label+': indisponível ('+type(exc).__name__+').')
    report += ['A consulta feita dentro da empresa não comprova acesso externo. Validar com o Wi-Fi do iPhone desligado.',
               'Se o CRM local funcionar e o HTTPS falhar, revisar DNS, NAT 80/443, CGNAT e data/external/caddy.log com a TI.',
               'A porta 3000 deve permanecer sem encaminhamento no roteador.']
    output = root/'DIAGNOSTICO-IPHONE.txt'
    output.write_text('\n'.join(report)+'\n',encoding='utf-8-sig')
    print('\n'.join(report))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action',choices=['prepare','activate','diagnose'])
    args = parser.parse_args()
    try:
        action = args.action
        if not action:
            print('SAIS BLUE CRM — APP IPHONE E HTTPS\n1. Preparar app e gerar solicitação para Telium/TI\n2. Ativar HTTPS após DNS e roteador configurados\n3. Diagnosticar acesso externo')
            action = {'1':'prepare','2':'activate','3':'diagnose'}.get(input('Escolha a etapa: ').strip())
        if action=='prepare': prepare()
        elif action=='activate': activate()
        elif action=='diagnose': diagnose()
        else: raise ValueError('Escolha 1, 2 ou 3.')
    except Exception as exc:
        # Configuration and network failures never dump environment values or token-bearing URLs.
        print(str(exc) if isinstance(exc,ValueError) else 'Não concluído ('+type(exc).__name__+'). Consulte a TI ou execute Diagnosticar acesso externo.')
    input('\nPressione Enter para fechar. ')


if __name__=='__main__':
    main()
