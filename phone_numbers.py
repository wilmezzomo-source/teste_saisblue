"""Phone comparison without changing a contact's verified WhatsApp identifier."""
import re

BRAZIL_DDDS=set('11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99'.split())


def digits(value):
    number=re.sub(r'[^0-9]','',str(value or ''))
    return number[2:] if number.startswith('00') else number


def brazil_national(number):
    if number[:2] not in BRAZIL_DDDS:return False
    subscriber=number[2:]
    return bool(re.fullmatch(r'[2-9][0-9]{7}',subscriber) or re.fullmatch(r'9[0-9]{8}',subscriber))


def manual_phone(value):
    raw=str(value or '').strip()
    number=digits(raw)
    if not raw.startswith(('+','00')) and brazil_national(number):
        number='55'+number
    if not 10<=len(number)<=15 or number.startswith('0'):
        raise ValueError('Informe um WhatsApp com DDI válido. Para o Brasil, use 55, DDD e telefone.')
    return number


def phone_identity(value):
    number=digits(value)
    if number.startswith('55') and len(number) in (12,13) and number[2:4] in BRAZIL_DDDS:
        subscriber=number[4:]
        # Old Brazilian mobile wa_ids can omit the ninth digit. Never add it
        # to a landline, and never apply Brazilian rules to another country.
        if re.fullmatch(r'[6-9][0-9]{7}',subscriber):
            return number[:4]+'9'+subscriber
    return number


def legacy_brazil_variants(value):
    number=phone_identity(value)
    if not number.startswith('55') or not brazil_national(number[2:]):return ()
    national=number[2:]
    variants=[national]
    if len(national)==11 and national[2]=='9' and national[3] in '6789':
        variants.append(national[:2]+national[3:])
    return tuple(variants)
