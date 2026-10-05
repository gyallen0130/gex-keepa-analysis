import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ui.smoke import collect_gex_sample, run_local_check
from keepa.parser import yen_from_keepa, basic_product_fields
from analysis.service import analyze_buybox
from tests.test_matcher import Fake

class Client(Fake):
    total_tokens_consumed = 1
    last_tokens_left = 20
    def __enter__(self): return self
    def __exit__(self,*args): pass

class Tests(unittest.TestCase):
    def test_japanese_yen_units(self):
        self.assertEqual(yen_from_keepa(1980),1980)
        for value in [None,-1,-2,float('nan'),float('inf')]:
            self.assertIsNone(yen_from_keepa(value))
        row=basic_product_fields({'stats':{'current':[1980,2000]}})
        self.assertEqual(row['Amazon現在価格'],1980)
        self.assertEqual(row['新品現在価格'],2000)

    def test_buybox_shipping_and_units(self):
        grouped=[{'asin':'A','amazon':{'Amazon現在':'あり'},'links':[]}]
        fake=Fake([{'products':[{'asin':'A','stats':{'buyBoxPrice':1980,'buyBoxShipping':200,'buyBoxSellerId':'OTHER'}}]}])
        self.assertEqual(analyze_buybox(grouped,fake)['rows'][0]['現在カート価格'],2180)
        fake=Fake([{'products':[{'asin':'A','stats':{'buyBoxPrice':1980,'buyBoxShipping':-2,'buyBoxSellerId':'OTHER'}}]}])
        self.assertIsNone(analyze_buybox(grouped,fake)['rows'][0]['現在カート価格'])

    def test_sample_does_not_crawl_all(self):
        from collectors import gex
        root=gex.OFFICIAL_ROOTS['アクアリウム']
        html=''.join(f'<a href="?m=ProductListDetail&id={i}">p</a>' for i in range(50))
        def parse(section,url):
            code='1234567'+gex.query_value(url,'id')
            return [{'公式商品名':'A','JANコード':code,'公式商品名':'A','公式カテゴリ':'','公式商品ページ':url,'公式区分':section,'公式商品ID':'1','公式カテゴリID':''}]
        with patch.object(gex,'request_html',return_value=html), patch.object(gex,'parse_official_product',side_effect=parse) as mock:
            result=collect_gex_sample(limit=5)
        self.assertEqual(len(result['products']),5)
        self.assertEqual(mock.call_count,5)
        self.assertEqual(result['list_pages'],1)

    def test_local_report_no_key_and_not_fake_bb_success(self):
        key='do-not-store-this-key'
        client=Client([{'products':[{'asin':'A','eanList':['12345678'],'stats':{'current':[-1,1980]}}]}])
        with tempfile.TemporaryDirectory() as directory:
            path,report_path,report=run_local_check([{'manufacturer':'GEX','jan':'12345678'}],key,output_dir=directory,client_factory=lambda _:client)
            self.assertTrue(path.exists())
            self.assertEqual(report['bb_status'],'NOT_VERIFIED')
            self.assertEqual(report['api_status'],'RESPONDED')
            self.assertNotIn(key,report_path.read_text())

    def test_api_errors_are_visible_in_report(self):
        client=Client([RuntimeError('private error')])
        with tempfile.TemporaryDirectory() as directory:
            _,_,report=run_local_check([{'jan':'12345678'}],'key',output_dir=directory,client_factory=lambda _:client)
            self.assertEqual(report['api_status'],'ERRORS')
            self.assertEqual(report['jan_errors'],1)
