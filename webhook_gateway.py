"""Local gateway: exposes only the signed WhatsApp callback, never CRM/API routes."""
import hashlib
import hmac
import ipaddress
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, jsonify, request

OFFICIAL_PHONE_ID='321395016679053'


def backend_url(values):
    host=values.get('CRM_LISTEN_HOST') or urllib.parse.urlsplit(values.get('APP_URL','')).hostname or '127.0.0.1'
    address=ipaddress.ip_address(host)
    allowed=address.is_loopback or any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
    if address.version!=4 or not allowed:
        raise ValueError('O gateway precisa apontar para o IPv4 local do CRM, nunca para um destino público.')
    return f'http://{host}:3000'


def validate_config(values):
    if values.get('META_PHONE_NUMBER_ID')!=OFFICIAL_PHONE_ID:
        raise ValueError('Configure o Phone Number ID oficial 321395016679053 antes de abrir o gateway.')
    if not values.get('META_APP_SECRET') or not values.get('META_VERIFY_TOKEN'):
        raise ValueError('Configure App Secret e token de verificação antes de abrir o gateway.')
    return backend_url(values)


def probe_backend(values,sender=urllib.request.urlopen):
    base=validate_config(values)
    challenge=secrets.token_hex(16)
    query=urllib.parse.urlencode({'hub.mode':'subscribe','hub.verify_token':values['META_VERIFY_TOKEN'],'hub.challenge':challenge})
    try:
        with sender(base+'/webhooks/whatsapp?'+query,timeout=5) as response:
            if response.read().decode()!=challenge:
                raise ValueError('A verificação local não retornou o desafio esperado.')
        body=b'{"object":"whatsapp_business_account","entry":[]}'
        signature='sha256='+hmac.new(values['META_APP_SECRET'].encode(),body,hashlib.sha256).hexdigest()
        req=urllib.request.Request(base+'/webhooks/whatsapp',data=body,headers={'Content-Type':'application/json','X-Hub-Signature-256':signature})
        with sender(req,timeout=5) as response:
            if json.load(response).get('ok') is not True:
                raise ValueError('A aplicação não confirmou o evento vazio de verificação.')
    except (OSError,ValueError,KeyError):
        raise ValueError('O CRM ainda não confirmou a configuração Meta. Pare e reinicie INICIAR-NO-WINDOWS.cmd após salvar as credenciais e tente novamente.') from None
    return base


def create_gateway(values,sender=None):
    base=validate_config(values)
    transport=sender or urllib.request.urlopen
    app=Flask(__name__,static_folder=None)
    app.config['MAX_CONTENT_LENGTH']=1_000_000

    @app.after_request
    def safe_headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.route('/webhooks/whatsapp',methods=['GET','POST'])
    def forward():
        if request.method=='GET':
            token=request.args.get('hub.verify_token','')
            if request.args.get('hub.mode')!='subscribe' or not hmac.compare_digest(token,values['META_VERIFY_TOKEN']):
                return jsonify(error='Verificação inválida.'),403
            query=urllib.parse.urlencode({key:request.args.get(key,'') for key in ('hub.mode','hub.verify_token','hub.challenge')})
            target=urllib.request.Request(base+'/webhooks/whatsapp?'+query)
        else:
            body=request.get_data()
            signature=request.headers.get('X-Hub-Signature-256','')
            expected='sha256='+hmac.new(values['META_APP_SECRET'].encode(),body,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,expected):
                return jsonify(error='Assinatura inválida.'),403
            target=urllib.request.Request(base+'/webhooks/whatsapp',data=body,headers={'Content-Type':'application/json','X-Hub-Signature-256':signature})
        try:
            with transport(target,timeout=25) as upstream:
                return Response(upstream.read(1_000_001),status=upstream.status,content_type=upstream.headers.get('Content-Type','application/json'))
        except urllib.error.HTTPError as error:
            return jsonify(error='O CRM recusou o evento.'),error.code
        except (OSError,ValueError):
            return jsonify(error='O CRM não respondeu. Tente novamente mais tarde.'),502

    return app
