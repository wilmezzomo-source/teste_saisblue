"""Local conversation helpers. No model downloads, API keys or external requests."""
import re

from qualification_location import normalize, accumulate_location

LABEL_PROFILE='Marca própria (PL/WL)'
LABEL_WAIT=15*60


def is_label_interest(body):
    for clause in re.split(r'[,;.!?\n]+',body):
        value=normalize(clause)
        for match in re.finditer(r'\b(?:white\s*label|private\s*label|pl|wl|marca propria|producao (?:para|pra) (?:a )?minha marca)\b',value):
            prefix=re.split(r'\b(?:mas|porem|e sim)\b',value[:match.start()])[-1]
            negated={'nao','nem'}.intersection(prefix.split()[-3:]) or re.search(r'\b(?:nao|nem) (?:tenho|tem|ha) (?:interesse|necessidade) (?:em|de)\s*$',prefix)
            if not negated:return True
    return False


def conversation_location(body, pending_city='', pending_state=''):
    """Recognize location clauses without mistaking the rest of a sentence for a city."""
    original=accumulate_location(body,pending_city,pending_state)
    if original[2] or original[:2]!=(pending_city,pending_state):return original
    raw=normalize(body)
    candidates=[s.strip() for s in re.split(r'[,.!;?\n]+',body) if s.strip()]
    for cue in re.finditer(r'\b(?:sou de|moro em|moro no|moro na|minha cidade e|cidade de|estou em|fico em|fica em|em) ',raw):
        if {'nao','nem'}.intersection(raw[:cue.start()].split()[-2:]):continue
        candidates.append(raw[cue.end():])
    for candidate in candidates:
        words=normalize(candidate).split()
        # Longest prefix first: an explicitly inconsistent UF must never be
        # discarded just to infer a different state from the shortened city.
        for count in range(min(12,len(words)),0,-1):
            place=accumulate_location(' '.join(words[:count]),pending_city,pending_state)
            if place[2] or place[:2]!=(pending_city,pending_state):return place
    return original


def answer_intent(body):
    value=normalize(body)
    for intent,pattern in (
        ('identity',r'\b(?:voce e (?:um )?(?:robo|bot|ia)|e automatico|e uma pessoa)\b'),
        ('volume',r'\b(?:o que (?:e|significa) volume|como assim (?:volume|pecas mensais))\b'),
        ('brand',r'\b(?:o que (?:e|significa) (?:marca|white label|private label)|como funciona (?:o )?(?:pl|wl|white label|private label))\b'),
        ('catalog',r'\b(?:catalogo|modelos|colecao|tamanhos|tecidos|composicao|tem legging|tem vestido|tem top|quais pecas)\b'),
        ('prices',r'\b(?:preco|precos|valor|valores|pedido minimo|minimo de pecas|atacado|condicoes|frete|prazo|entrega|pagamento|parcelamento|cartao|pix)\b'),
        ('human',r'\b(?:falar com (?:uma )?(?:pessoa|consultora|vendedora|humano)|quero (?:uma )?(?:consultora|vendedora))\b'),
        ('clarify',r'\b(?:nao entendi|nao compreendi|pode explicar|como assim|nao sei responder)\b'),
        ('greeting',r'^(?:oi|ola|bom dia|boa tarde|boa noite|tudo bem|tudo bom)(?: tudo bem| tudo bom| e voce| obrigada| obrigado| sim)*$'),
        ('ack',r'^(?:ok|certo|entendi|obrigada|obrigado|valeu|beleza|sim|ta bom|tudo certo)(?: obrigada| obrigado| sim| ok)*$'),
    ):
        if re.search(pattern,value):return intent
    return ''


def conversational_reply(body, profile, previous_profile, pending_city, pending_state, question, first=False):
    intent=answer_intent(body)
    acknowledgements={
        'identity':'Sou o assistente virtual da Sais Blue e estou organizando seu atendimento para a equipe.',
        'volume':'É a quantidade aproximada de peças que sua marca vende ou movimenta por mês. Uma estimativa já ajuda; se ainda não souber, tudo bem.',
        'brand':'São peças produzidas para serem vendidas com a identidade da sua marca. A equipe confirma os detalhes e a viabilidade do projeto com você.',
        'catalog':'Vou registrar seu interesse no catálogo para a consultora te apresentar as opções.',
        'prices':'A consultora poderá te orientar sobre valores, condições e disponibilidade. Vou registrar sua dúvida junto do atendimento.',
        'human':'Vou registrar sua solicitação para uma consultora dar continuidade por aqui.',
        'clarify':'Sem problema! Vou perguntar só o que falta para direcionar sua conversa.',
    }
    acknowledgement=acknowledgements.get(intent,'')
    if not acknowledgement and profile and profile!=previous_profile:
        acknowledgement={
            'Consumidor Final':'Entendi, as peças são para seu uso.',
            'Revenda':'Que bom! Vou registrar seu interesse em revender.',
            'Lojista':'Certo, você está buscando peças para sua loja.',
            LABEL_PROFILE:'Entendi seu interesse em marca própria.',
        }.get(profile,'')
    if not acknowledgement and intent=='greeting' and not first:
        acknowledgement='Tudo certo por aqui! Vamos continuar seu atendimento.'
    if first:
        greeting=next((text for key,text in (('bom dia','Bom dia!'),('boa tarde','Boa tarde!'),('boa noite','Boa noite!')) if key in normalize(body)),'Oi!')
        intro=greeting+' Sou o assistente virtual da Sais Blue.'
        return ' '.join(p for p in (intro,acknowledgement,question) if p),intent
    return ' '.join(p for p in (acknowledgement,question) if p),intent


def label_details(body, previous=None, *, free_answer=False, asked_field='both'):
    data=dict(previous or {})
    raw=body.strip()
    value=normalize(raw)
    if not value:return data
    brand=re.search(r'\b(?:minha\s+|a\s+)?marca(?:\s+(?:se chama|chama se|chama|e|é)\b\s*|\s*[:=]\s*)(.+)',raw,re.I)
    if brand:
        name=re.split(r'[,;\n!]|\.(?=\s|$)|\s+(?:e\s+)?(?:giro|giramos|movimento|movimentamos|volume|vendo|vendemos|produzo|produzimos)\b|\s+\d[\d.,]*\s*(?:pecas|peças|unidades)',brand.group(1),maxsplit=1,flags=re.I)[0].strip(' :"\'')
        if name and not re.match(r'^(?:nao|não|ainda|sem)\b',name,re.I):data['brand']=name[:200]
    numeric=r'(?:\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?)\s*(?:mil|k)?(?:\s*(?:a|ate|até|-)\s*\d[\d.,]*\s*(?:mil|k)?)?'
    volume=re.search(r'('+numeric+r')\s*(?:pecas|peças|unidades)\b(?:\s*(?:por|ao|no|/|mensais|mensalmente)\s*(?:mes|mês|semana|dia|ano)?)?',raw,re.I)
    if not volume:
        volume=re.search(r'\b(?:volume|giro|giro mensal|movimento|vendo|vendemos|produzo|produzimos)\s*(?:de|e|é|:)?\s*('+numeric+r')\b',raw,re.I)
    if not volume:
        volume=re.search(r'('+numeric+r')\s*(?:(?:por|ao|no|/)\s*(?:mes|mês)|mensais|mensalmente)\b',raw,re.I)
    if not volume and free_answer and not re.search(r'r\$|reais|preco|preço',raw,re.I):
        volume=re.fullmatch(r'\s*('+numeric+r')\s*(?:por mes|por mês|mensais|/mes|/mês)?\s*',raw,re.I)
    if volume and re.search(r'r\$|\breais\b',raw,re.I) and not re.search(r'\b(?:pecas|peças|unidades)\b',raw,re.I):volume=None
    if volume:
        amount=volume.group(0).strip()
        period=next((period for period in ('semana','dia','ano') if re.search(r'\b'+period+r'\b',normalize(amount))),None)
        quantity=volume.group(1).strip()
        data['volume']=(quantity+' peças/'+period+' (mensal não informado)' if period else quantity+' peças/mês')[:250]
    refused=value in ('nao','sem dados','n a') or bool(re.search(r'\b(?:nao sei|nao tenho|nao possuo|nao defini|ainda nao|sem estimativa|prefiro nao|nao quero informar|nao informar|nao vou informar|nao posso informar|nao gostaria de informar|nao informado|nao informada|desconheco)\b',value))
    if refused:
        field_specific=any(word in value for word in ('marca','volume','quantidade','pecas'))
        if ('marca' in value or not field_specific) and not data.get('brand'):data['brand_declined']=True
        if (any(word in value for word in ('volume','quantidade','pecas')) or not field_specific) and not data.get('volume'):data['volume_declined']=True
    if free_answer and not brand and not volume and not refused and asked_field in ('both','brand'):
        # A short direct reply to the brand question is a name, not a new profile
        # or location. Questions/greetings and unfinished prefixes are not names.
        unrelated=bool(re.search(r'\b(?:meu nome|me chamo|sou de|moro em|minha cidade|meu estado|reais)\b',value) or 'r$' in raw.lower())
        if not unrelated and not answer_intent(raw) and '?' not in raw and len(value.split())<=8 and value not in ('sim','nao','ok','minha marca','a marca','marca','so um momento','pl','wl','private label','white label','marca propria'):
            data['brand']=raw[:200]
    # A split answer may contain the brand before a numeric volume in one line.
    if free_answer and volume and not data.get('brand') and asked_field in ('both','brand'):
        prefix=raw[:volume.start()].strip(' ,;:-')
        if prefix and len(prefix.split())<=8 and not re.search(r'\b(?:giro|volume|vendo|produzo|movimento)\b',normalize(prefix)):
            data['brand']=prefix[:200]
    return data


def label_complete(data):
    return bool((data.get('brand') or data.get('brand_declined')) and (data.get('volume') or data.get('volume_declined')))


def label_question(data):
    if data.get('brand') or data.get('brand_declined'):
        return 'E qual é o volume aproximado de peças que a marca movimenta por mês? Se ainda não souber, pode me dizer e seguimos mesmo assim.'
    if data.get('volume') or data.get('volume_declined'):
        return 'Qual é o nome da sua marca? Se ainda não tiver definido, tudo bem.'
    return 'Qual é a sua marca e, aproximadamente, quantas peças ela movimenta por mês? Se ainda não tiver essas informações, tudo bem.'


def label_note(data):
    return 'Interesse: Marca própria (White/Private Label)\nMarca: '+data.get('brand','Não informada')+'\nVolume mensal: '+data.get('volume','Não informado')


def merge_managed_note(note, old, new):
    if old and old in note:return note.replace(old,new,1).strip()
    if new and new not in note:return (note.rstrip()+'\n\n'+new).strip()
    return note
