"""不明な容量・入数を一致扱いしない規格比較。"""
import re
import unicodedata
from decimal import Decimal
ALIASES={'サフ':['saf','lesaffre'],'サバトン':['sabaton'],'ボワロン':['boiron'],'カカオバリー':['cacao barry']}
def norm(v):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v or '')).casefold()).strip()
def quantities(v):
    units={'kg':('g',1000),'g':('g',1),'ml':('ml',1),'l':('ml',1000)}
    return {(units[u][0],Decimal(n)*units[u][1]) for n,u in re.findall(r'(\d+(?:\.\d+)?)\s*(kg|ml|g|l)(?![a-z])',norm(v))}
def evaluate(p,c):
    title=norm(c.get('title'));brand=norm(p.get('brand'));actual=norm(c.get('brand'))
    aliases=[brand]+[norm(v) for v in ALIASES.get(p.get('brand'),[])]
    checks={'ブランド': '一致' if brand and (actual in aliases or any(v and v in title for v in aliases)) else '不一致' if brand and actual else '不明'}
    model=norm(p.get('model_number'));name=norm(p.get('product_name'))
    checks['商品名・型番']='一致' if (model and model in title) or (name and name in title) else '不明'
    want=quantities(p.get('unit_capacity') or p.get('capacity'));have=quantities(title)
    checks['容量']='一致' if want and have==want else '不一致' if want and have and not want.intersection(have) else '不明'
    counts=re.findall(r'(\d+)\s*(?:個|袋|缶|本|パック|枚)(?:入り|入|セット|組)?',title)+re.findall(r'[×x]\s*(\d+)',title)+re.findall(r'(\d+)\s*セット',title)
    count=norm(p.get('sales_units'));other=counts[0] if len(set(counts))==1 else ''
    checks['販売単位']='一致' if count and count==other else '不一致' if count and other else '不明'
    for field,label in [('variant','味・種類'),('color','色'),('size','サイズ')]:
        v=norm(p.get(field))
        if v:checks[label]='一致' if v in title else '不明'
    if ('iqf' in name)!=('iqf' in title):checks['IQF']='不明'
    if '無加糖' in name and '加糖' in title and '無加糖' not in title:checks['加糖']='不一致'
    for suffix in ['%','度']:
        a=re.findall(r'(\d+(?:\.\d+)?)\s*'+suffix,name);b=re.findall(r'(\d+(?:\.\d+)?)\s*'+suffix,title)
        if a:checks['比率・度数'+suffix]='一致' if a==b else '不一致' if b else '不明'
    status='別規格・除外' if '不一致' in checks.values() else '有力候補・未承認' if all(v=='一致' for v in checks.values()) else '要確認'
    return {'評価':status,'比較結果':checks,'評価理由':' / '.join(f'{k}:{v}' for k,v in checks.items())}
def search_terms(p,limit=2):
    brand=norm(p.get('brand'));name=norm(p.get('product_name'));model=norm(p.get('model_number'))
    if len(name)<3 or (not brand and not model):return []
    capacity=norm(p.get('unit_capacity') or p.get('capacity'))
    keywords=norm(p.get('search_keywords'))
    base=' '.join(filter(None,[brand,name,model,norm(p.get('variant')),norm(p.get('color'))]))
    return list(dict.fromkeys([keywords or (base+' '+capacity).strip(),base]))[:limit]
