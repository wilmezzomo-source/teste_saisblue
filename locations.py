"""Municipality catalog: deterministic coordinates, no customer data sent to geocoders."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CITIES = json.loads((Path(__file__).parent / 'public/data/cities.json').read_text(encoding='utf-8'))
CITY_BY_ID = {city['id']: city for city in CITIES}
STATES = sorted({city['state'] for city in CITIES})


def location_fields(city_id):
    city = CITY_BY_ID.get(str(city_id or ''))
    if city is None:
        raise ValueError('Selecione uma cidade e estado válidos. A localização é obrigatória.')
    return {'city_id':city['id'], 'city':city['name'], 'state':city['state']}


def instagram_handle(value):
    if not isinstance(value,str):
        raise ValueError('Informe o usuário ou link do Instagram.')
    value=value.strip()
    if not value:
        return ''
    if value.startswith(('https://','http://','www.instagram.com/','instagram.com/')):
        parsed=urlsplit(value if value.startswith(('https://','http://')) else 'https://'+value)
        if parsed.hostname not in ('instagram.com','www.instagram.com'):
            raise ValueError('Use um perfil de instagram.com, não outro site.')
        value=parsed.path.strip('/')
    value=value.removeprefix('@')
    if not re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?',value) or '..' in value:
        raise ValueError('Informe um usuário válido do Instagram (até 30 caracteres).')
    return value.lower()
