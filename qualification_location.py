"""Recognize Brazilian municipalities; infer UF only from a unique catalog match."""
import re
import unicodedata
from locations import CITIES

STATE_NAMES = dict(zip(
    ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'),
    ('Acre','Alagoas','Amapá','Amazonas','Bahia','Ceará','Distrito Federal','Espírito Santo','Goiás','Maranhão','Mato Grosso','Mato Grosso do Sul','Minas Gerais','Pará','Paraíba','Paraná','Pernambuco','Piauí','Rio de Janeiro','Rio Grande do Norte','Rio Grande do Sul','Rondônia','Roraima','Santa Catarina','São Paulo','Sergipe','Tocantins')))


def normalize(value):
    value=''.join(c for c in unicodedata.normalize('NFKD',value.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',value).strip()


CITY_LOOKUP = {(normalize(c['name']),c['state']):c for c in CITIES}
CITY_NAMES = {name for name, uf in CITY_LOOKUP}
STATE_ALIASES = {normalize(name):uf for uf,name in STATE_NAMES.items()}
STATE_ALIASES.update({uf.lower():uf for uf in STATE_NAMES})
BY_NAME, ABBREVIATED = {}, {}
for city in CITIES:
    name=normalize(city['name'])
    BY_NAME.setdefault(name,[]).append(city)
    # A known omission, not fuzzy spelling: "Ocidental Goiás" means Cidade Ocidental.
    if name.startswith('cidade '):
        ABBREVIATED.setdefault(name[7:],[]).append(city)


def variants(body):
    raw=normalize(body)
    values=[raw]
    prefixes=(r'^(?:(?:eu )?sou de|(?:eu )?moro (?:em|no|na)|minha cidade e|meu municipio e|cidade de|cidade|municipio) ',
              r'^(?:eu )?(?:sou|trabalho como) (?:lojista|revendedor|revendedora) (?:e )?(?:sou de|moro em|de|em) ')
    for prefix in prefixes:
        for value in tuple(values):
            clean=re.sub(prefix,'',value)
            if clean not in values: values.append(clean)
    for cue in re.finditer(r'\b(?:sou de|moro em|minha cidade e|meu municipio e) ',raw):
        before=raw[:cue.start()].split()
        if before and before[-1] in ('nao','nem'):
            continue
        tail=raw[cue.end():]
        if tail not in values: values.append(tail)
    return values


def named_candidates(name, state=''):
    # A real, complete name always wins over an abbreviated name.
    exact=BY_NAME.get(name,[])
    rows=exact or ABBREVIATED.get(name,[])
    return [c for c in rows if not state or c['state']==state]


def split_pair(body):
    for value in variants(body):
        for state,uf in sorted(STATE_ALIASES.items(),key=lambda pair:-len(pair[0])):
            if value.endswith(' '+state):
                name=value[:-(len(state)+1)].strip()
                name=re.sub(r'(?: (?:no|na|em|de|do|da|estado|uf))+$','',name)
                rows=named_candidates(name,uf)
                if len(rows)==1:
                    city=rows[0]
                    return normalize(city['name']),uf,city
                # Remember an explicit but inconsistent UF. Never silently replace it.
                candidates=named_candidates(name)
                official={normalize(c['name']) for c in candidates}
                if len(official)==1:
                    return next(iter(official)),uf,None
    return None


def whole_city_candidates(body):
    for value in variants(body):
        rows=named_candidates(value)
        if rows:
            return rows
    return []


def parse_city(body):
    # An official name may itself end with a state: Santa Maria do Pará, for example.
    rows=whole_city_candidates(body)
    if rows:
        return rows[0] if len(rows)==1 else None
    pair=split_pair(body)
    return pair[2] if pair else None


def accumulate_location(body,pending_city='',pending_state=''):
    raw=normalize(body)
    explicit_state=re.sub(r'^(?:meu estado e|o estado e|estado de|estado|uf|sou do|e) ','',raw)
    state_introduced=explicit_state!=raw
    rows=whole_city_candidates(body)
    is_state=explicit_state in STATE_ALIASES and (state_introduced or (pending_city and not pending_state) or not rows)
    if is_state:
        pending_state=STATE_ALIASES[explicit_state]
    elif rows:
        official={normalize(c['name']) for c in rows}
        if len(official)==1:
            pending_city=next(iter(official))
    else:
        pair=split_pair(body)
        if pair:
            return pair
    rows=named_candidates(pending_city,pending_state)
    if len(rows)==1:
        city=rows[0]
        return normalize(city['name']),city['state'],city
    return pending_city,pending_state,None


def display_city(name):
    rows=named_candidates(name)
    return rows[0]['name'] if rows else name
