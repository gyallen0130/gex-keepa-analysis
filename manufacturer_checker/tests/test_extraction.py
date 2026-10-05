import unittest
from unittest.mock import patch
import requests
from collectors import gex
from keepa.client import KeepaClient
class Response:
 def __init__(self,data,status=200):self.data,self.status_code=data,status
 def json(self):return self.data
 def raise_for_status(self):pass
class Session:
 def __init__(self,items):self.headers={};self.items=iter(items);self.calls=[]
 def get(self,url,**kw):
  self.calls.append((url,kw));item=next(self.items)
  if isinstance(item,Exception):raise item
  return item
 def close(self):pass
class Tests(unittest.TestCase):
 def test_multiple_jan(self):
  html='<h1 class="c-detail__ttl">商品A</h1><table><tr><th>JANコード</th><td>4972547123456 / 4972547123457</td></tr><tr><th>コード</th><td>A-12</td></tr></table>'
  with patch.object(gex,'request_html',return_value=html):rows=gex.parse_official_product('魚','https://product.gex-fp.co.jp/fish/?id=12')
  self.assertEqual(len(rows),2);p=gex.to_common_product(rows[0]);self.assertEqual(p['manufacturer_code'],'A-12');self.assertEqual(p['model_number'],'')
 def test_missing_jan(self):
  with patch.object(gex,'request_html',return_value='<h1 class="c-detail__ttl">商品B</h1>'):rows=gex.parse_official_product('魚','https://product.gex-fp.co.jp/fish/?id=1')
  self.assertEqual(len(rows),1);self.assertEqual(gex.to_common_product(rows[0])['jan'],'')
 def test_discovery(self):
  root='https://product.gex-fp.co.jp/fish/';listing=root+'?m=ProductList&cid=1';detail=root+'?m=ProductListDetail&id=2'
  pages={root:f'<a href="{listing}">list</a>',gex.canonicalize_url(listing):f'<a href="{listing}">cycle</a><a href="{detail}">detail</a><a href="https://other.test/fish/?m=ProductListDetail&id=3">other</a>'}
  with patch.object(gex,'request_html',side_effect=lambda u:pages[u]):urls,errors,count=gex.discover_detail_urls('魚',root)
  self.assertEqual(urls,[gex.canonicalize_url(detail)]);self.assertEqual(errors,[]);self.assertEqual(count,2)
 def test_429_resume(self):
  session=Session([Response({'tokensLeft':0,'refillRate':20},429),Response({'tokensLeft':10,'tokensConsumed':1})]);waits=[]
  client=KeepaClient('fake-key',session=session,sleep=waits.append,logger=lambda _:None);params={'domain':5,'code':'4972547123456'}
  self.assertEqual(client.keepa_get_with_wait('/product',params,1,'test')['tokensLeft'],10)
  self.assertEqual(session.calls[0],session.calls[1]);self.assertNotIn('key',params);self.assertEqual(client.total_tokens_consumed,1);self.assertTrue(waits)
  self.assertIsNone(KeepaClient('other',session=Session([])).last_tokens_left)
 def test_key_redaction(self):
  logs=[];session=Session([requests.ConnectionError('https://api.keepa.com/product?key=secret-test') for _ in range(2)])
  client=KeepaClient('secret-test',session=session,sleep=lambda _:None,logger=logs.append)
  with self.assertRaises(RuntimeError) as caught:client.keepa_get('/product',{},retry=2)
  self.assertNotIn('secret-test',str(caught.exception));self.assertNotIn('secret-test',' '.join(logs))
 def test_collector_empty(self):self.assertEqual(gex.GexCollector({}).collect(),[])
