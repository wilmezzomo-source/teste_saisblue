"""Validate an HTTPS callback without exposing credentials or opening the CRM UI."""
import secrets
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def callback_url(value):
    parsed=urllib.parse.urlsplit(value.strip())
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None,443):
        raise ValueError('Use a URL HTTPS pública fornecida pelo túnel, sem usuário, senha ou parâmetros.')
    if parsed.path.rstrip('/') not in ('','/webhooks/whatsapp'):
        raise ValueError('Use a raiz da URL HTTPS do túnel ou o caminho /webhooks/whatsapp.')
    return 'https://'+parsed.netloc+'/webhooks/whatsapp'


def verify_public(value,verification_token,sender=None):
    url=callback_url(value)
    transport=sender or urllib.request.build_opener(NoRedirect()).open
    challenge=secrets.token_hex(20)
    query=urllib.parse.urlencode({'hub.mode':'subscribe','hub.verify_token':verification_token,'hub.challenge':challenge})
    req=urllib.request.Request(url+'?'+query,headers={'User-Agent':'SaisBlueCRM-WebhookCheck/1.0','ngrok-skip-browser-warning':'1'})
    try:
        with transport(req,timeout=15) as response:
            if response.status!=200 or response.read(5000).decode()!=challenge:
                raise ValueError('A URL não confirmou o desafio de verificação.')
        # In the tunnel mode the root and API must not expose the application.
        origin=urllib.parse.urlsplit(url)
        root='https://'+origin.netloc
        for path in ('/','/api/contacts','/login'):
            try:
                with transport(urllib.request.Request(root+path,headers={'ngrok-skip-browser-warning':'1'}),timeout=5):
                    raise ValueError('O túnel está expondo a aplicação inteira. Aponte o ngrok para a porta 3002 do gateway.')
            except urllib.error.HTTPError as error:
                if error.code!=404:
                    raise ValueError('As rotas privadas não estão isoladas pelo gateway. Confira a porta do túnel.') from None
    except urllib.error.HTTPError as error:
        raise ValueError(f'A URL pública recusou a verificação (HTTP {error.code}). Confira se o CRM e o túnel estão abertos.') from None
    except OSError:
        raise ValueError('A URL pública não respondeu. Confira internet, conta ngrok e as janelas do CRM/túnel.') from None
    return url
