import unittest
from matchers.jan_matcher import lookup_by_jan
from keepa.parser import basic_product_fields
class Fake:
 def __init__(self,responses):self.responses=iter(responses);self.calls=[]
 def keepa_get_with_wait(self,*args):
  self.calls.append(args);r=next(self.responses)
  if isinstance(r,Exception):raise r
  return r
class Tests(unittest.TestCase):
 def test_many_to_many_and_unrelated(self):
  products=[{'manufacturer':'GEX','jan':'4972547123456'},{'manufacturer':'別メーカー','jan':'4972547123456'},{'jan':'0490123456789'}]
  f=Fake([{'products':[{'asin':'A','eanList':['4972547123456','490123456789']},{'asin':'B','eanList':['4972547123456']},{'asin':'C','eanList':['99999999']}]}])
  r=lookup_by_jan(products,f)
  self.assertEqual(len(r['matched']),5);self.assertEqual(len(r['asin_products']),2)
  self.assertEqual(len(r['asin_products'][0]['links']),3);self.assertEqual(r['summary']['matched_source_products'],3)
  self.assertEqual(len(f.calls),1);self.assertNotIn('match_status',products[0])
 def test_statuses(self):
  ps=[{'jan':''},{'jan':'bad'},{'jan':'12345678'},{'jan':'23456789'},{'jan':'34567890'}]
  r=lookup_by_jan(ps,Fake([{'products':[]},RuntimeError('secret')]),batch_size=1,limit=2)
  self.assertEqual([x['match_status'] for x in r['unresolved']],['INSUFFICIENT_DATA','INSUFFICIENT_DATA','NO_CANDIDATE','LOOKUP_ERROR','NOT_SCANNED'])
  self.assertNotIn('secret',str(r))
 def test_bad_response_is_error(self):
  r=lookup_by_jan([{'jan':'12345678'}],Fake([{}]))
  self.assertEqual(r['unresolved'][0]['match_status'],'LOOKUP_ERROR')
 def test_batch_and_no_jan(self):
  f=Fake([{'products':[]},{'products':[]}]);lookup_by_jan([{'jan':str(10000000+i)} for i in range(21)],f)
  self.assertEqual(len(f.calls),2)
  self.assertEqual(lookup_by_jan([{'jan':''}],Fake([]))['summary']['attempted_codes'],0)
 def test_parser(self):
  r=basic_product_fields({'asin':'A','stats':{'current':[-1,123400,-1,100]}})
  self.assertIsNone(r['Amazon現在価格']);self.assertEqual(r['新品現在価格'],123400)
