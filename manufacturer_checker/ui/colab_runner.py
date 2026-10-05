"""Colab用の共通実行処理。認証・入力はNotebook側で受け取る。"""
import json
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs
from keepa.client import KeepaClient
from matchers.jan_matcher import lookup_by_jan
from analysis.service import analyze_buybox
from output.excel_writer import write_excel


def parse_folder_id(value):
    value = str(value or '').strip()
    if value.startswith(('https://','http://')):
        url = urlparse(value)
        if url.hostname != 'drive.google.com':
            raise ValueError('Google DriveのフォルダURLを指定してください')
        match = re.search(r'/folders/([A-Za-z0-9_-]+)',url.path)
        value = match.group(1) if match else parse_qs(url.query).get('id',[''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,}',value):
        raise ValueError('保存先フォルダのURLまたはIDを確認してください')
    return value


def run_research(products, api_key, manufacturer, *, jan_limit=5, bb_limit=3,
                 min_other_share=0.1, output_dir='results', collector_errors=(),
                 input_warnings=(), client_factory=KeepaClient):
    if not products:
        raise ValueError('商品データが0件です。取得/入力を確認してください')
    if not str(manufacturer).strip():
        raise ValueError('メーカー名を指定してください')
    if jan_limit is not None and (not isinstance(jan_limit,int) or jan_limit < 0):
        raise ValueError('JAN件数は0以上、またはNone（全件）')
    if not isinstance(bb_limit,int) or bb_limit < 0:
        raise ValueError('BB件数は0以上')
    if not 0 <= min_other_share <= 100:
        raise ValueError('カート率閾値は0〜100%')
    name = re.sub(r'[^\w一-龥ぁ-んァ-ヶ-]+','_',str(manufacturer).strip())
    stamp = datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
    path = Path(output_dir)/f'{name}_{stamp}.xlsx'
    with client_factory(api_key) as client:
        matching=lookup_by_jan(products,client,limit=jan_limit)
        analysis=analyze_buybox(matching['asin_products'],client,limit=bb_limit,min_other_share=min_other_share)
        write_excel(path,products,matching,analysis,collector_errors=collector_errors,
                    input_warnings=input_warnings,tokens_consumed=client.total_tokens_consumed)
        report={**matching['summary'],'manufacturer':str(manufacturer).strip(),
                'jan_errors':len(matching['errors']),'bb_errors':len(analysis['errors']),
                'bb_received':sum(r['BB取得状態']=='RECEIVED' for r in analysis['rows']),
                'tokens_consumed':client.total_tokens_consumed,
                'drive_status':'NOT_UPLOADED','local_excel':str(path)}
    report_path=path.with_suffix('.json')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path,report_path,report
