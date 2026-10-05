"""JSON商品マスタ/GEX → JAN照合 → BB分析 → Excel。キーは環境変数。"""
import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from collectors.gex import GexCollector
from keepa.client import KeepaClient
from matchers.jan_matcher import lookup_by_jan
from analysis.service import analyze_buybox
from output.excel_writer import write_excel

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',help='商品一覧.xlsx/.csv/.tsv、または共通形式JSON。省略時はGEX公式取得')
    parser.add_argument('--manufacturer',default='GEX')
    parser.add_argument('--sheet-name',help='Excel入力シート名（既定:先頭シート）')
    parser.add_argument('--header-row',type=int,default=1)
    parser.add_argument('--column-map',help='共通項目→入力列名のJSONファイル')
    parser.add_argument('--output-dir',default='results')
    parser.add_argument('--drive-folder-id',help='ColabからDrive保存する親フォルダID')
    parser.add_argument('--jan-start',type=int,default=0)
    parser.add_argument('--jan-limit',type=int)
    parser.add_argument('--bb-limit',type=int,default=200)
    parser.add_argument('--min-other-share',type=float,default=0.1)
    args=parser.parse_args()
    if not os.environ.get('KEEPA_API_KEY'):parser.error('環境変数KEEPA_API_KEYを設定してください')
    if args.jan_start < 0 or (args.jan_limit is not None and args.jan_limit < 0) or args.bb_limit < 0 or not 0 <= args.min_other_share <= 100:
        parser.error('範囲・閾値が不正です')
    drive_service=None
    if args.drive_folder_id:
        from output.drive import build_colab_drive_service, validate_parent
        drive_service=build_colab_drive_service()
        validate_parent(drive_service,args.drive_folder_id)
    collector_errors=[]
    input_warnings=[]
    if args.input:
        if Path(args.input).suffix.lower() == '.json':
            products=json.loads(Path(args.input).read_text(encoding='utf-8'))
            if not isinstance(products,list) or any(not isinstance(p,dict) for p in products):parser.error('JSONは商品辞書の配列にしてください')
        else:
            from collectors.excel import ExcelCollector
            column_map=json.loads(Path(args.column_map).read_text(encoding='utf-8')) if args.column_map else None
            collector=ExcelCollector(args.input,args.manufacturer,sheet_name=args.sheet_name,header_row=args.header_row,column_map=column_map)
            products=collector.collect();input_warnings=collector.warnings
    else:
        if args.manufacturer != 'GEX':parser.error('他メーカーは--inputで商品マスタを指定してください')
        collector=GexCollector();products=collector.collect();collector_errors=collector.errors
    with KeepaClient(os.environ['KEEPA_API_KEY']) as client:
        matching=lookup_by_jan(products,client,start=args.jan_start,limit=args.jan_limit)
        analysis=analyze_buybox(matching['asin_products'],client,limit=args.bb_limit,min_other_share=args.min_other_share)
        # 同日再実行でも既存結果を上書きしない。
        import re
        name=re.sub(r'[^\w一-龥ぁ-んァ-ヶ-]+','_',args.manufacturer) or 'manufacturer'
        stamp=datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
        path=write_excel(Path(args.output_dir)/f'{name}_{stamp}.xlsx',products,matching,analysis,collector_errors=collector_errors,tokens_consumed=client.total_tokens_consumed,input_warnings=input_warnings)
    print(matching['summary']);print(f'ローカル保存完了: {path}')
    if drive_service is not None:
        from output.drive import upload_result
        saved=upload_result(drive_service,path,args.manufacturer,args.drive_folder_id)
        print('Drive保存完了:',saved.get('webViewLink') or saved['id'])
if __name__=='__main__':main()
