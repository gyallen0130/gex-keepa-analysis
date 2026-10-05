import tempfile
import unittest
from pathlib import Path
from openpyxl import Workbook
from collectors.excel import ExcelCollector
class Tests(unittest.TestCase):
 def test_utf8_and_missing_jan(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.csv';p.write_text('商品名,JANコード\n商品A,0012345678901\n商品B,\n,,\n',encoding='utf-8-sig')
   rows=ExcelCollector(p,'テスト').collect()
   self.assertEqual(len(rows),2);self.assertEqual(rows[0]['jan'],'0012345678901');self.assertEqual(rows[0]['manufacturer'],'テスト');self.assertEqual(rows[1]['source_row'],3)
 def test_cp932(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.csv';p.write_bytes('品名,JAN\n商品,12345678\n'.encode('cp932'))
   self.assertEqual(ExcelCollector(p).collect()[0]['product_name'],'商品')
 def test_tsv_and_invalid(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.tsv';p.write_text('product_name\tjan\nA\t1.23E+12\nB\t１２３４５６７８\n')
   c=ExcelCollector(p);rows=c.collect();self.assertEqual(rows[0]['jan'],'');self.assertEqual(rows[1]['jan'],'12345678');self.assertEqual(len(c.warnings),1)
 def test_xlsx_sheet_header_numeric_formula(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.xlsx';w=Workbook();s=w.active;s.title='商品一覧';s.append(['説明']);s.append(['商品名','JANコード']);s.append(['A',12345678]);s.append(['B','=12345678']);w.save(p)
   c=ExcelCollector(p,'メーカー',sheet_name='商品一覧',header_row=2);rows=c.collect()
   self.assertEqual(rows[0]['jan'],'12345678');self.assertEqual(rows[1]['jan'],'');self.assertEqual(len(c.warnings),2);self.assertEqual(rows[0]['source_sheet'],'商品一覧')
 def test_ambiguous_columns(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.csv';p.write_text('商品名,JAN,JANコード\nA,12345678,23456789\n')
   with self.assertRaises(ValueError):ExcelCollector(p).collect()
   rows=ExcelCollector(p,column_map={'jan':'JANコード'}).collect();self.assertEqual(rows[0]['jan'],'23456789')
 def test_missing_headers_and_sheet(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p.csv';p.write_text('foo\nbar\n')
   with self.assertRaises(ValueError):ExcelCollector(p).collect()
