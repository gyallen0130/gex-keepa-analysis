"""商品コードの安全な整理。数値セルの精度消失は自動補完しない。"""
import re
import unicodedata

def clean_code(value):
    if value is None:
        return ''
    if isinstance(value, bool) or isinstance(value, float):
        return ''
    text = unicodedata.normalize('NFKC', str(value)).strip()
    text = re.sub(r'[\s-]', '', text)
    return text if re.fullmatch(r'[0-9]{8,14}', text) else ''

def normalize_code(value):
    code = clean_code(value)
    return code.lstrip('0') if code else ''
