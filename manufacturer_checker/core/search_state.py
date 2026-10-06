"""検索状態の原子的保存と入力規格ハッシュ。"""
import hashlib,json,os,time
from pathlib import Path
VERSION=1
FIELDS=('manufacturer','brand','product_name','jan','manufacturer_code','model_number','capacity','unit_capacity','sales_units','variant','color','size','search_keywords')
def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def identity(p):
    content={k:str(p.get(k) or '').strip() for k in FIELDS};fp=digest(content)
    sid=digest([content['manufacturer'],content['manufacturer_code']]) if content['manufacturer_code'] else fp
    return sid,fp
class SearchState:
    def __init__(self,path,*,resume=True,sync=None):
        self.path=Path(path);self.sync=sync
        self.data={'version':VERSION,'queries':{},'reviews':{}}
        if resume and self.path.exists():self.data=json.loads(self.path.read_text(encoding='utf-8'))
        if self.data.get('version')!=VERSION:raise ValueError('検索状態の版が異なります')
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);temp=self.path.with_suffix('.tmp')
        with temp.open('w',encoding='utf-8') as f:
            json.dump(self.data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        temp.replace(self.path)
        if self.sync:self.sync(self.path)
    def query(self,term,*,force=False):
        key=digest({'version':VERSION,'domain':5,'term':term,'history':0,'stats':90,'update':48})
        entry=self.data['queries'].get(key)
        return key,(entry['products'] if entry and not force and time.time()-entry['time']<7*86400 else None)
    def put(self,key,products):
        self.data['queries'][key]={'time':time.time(),'products':products};self.save()
