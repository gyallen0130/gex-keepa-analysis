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
                 input_warnings=(), client_factory=KeepaClient, enable_name_search=False,
                 name_limit=20, name_query_limit=2, name_token_budget=400,
                 name_include_no_candidate=False, state_path=None, state_sync=None,
                 resume=True, force_research=False, review_path=None, jan_start=0):
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
    names = None
    from core.search_state import SearchState
    from matchers.name_matcher import read_reviews, lookup_by_name, merge_approved, refresh_approved
    reviews = read_reviews(review_path)
    if reviews and not enable_name_search:
        raise ValueError('確認Excelの利用には商品名検索を有効にしてください')
    if enable_name_search:
        if any(type(v) is not int or v < 0 for v in (name_limit,name_token_budget)) or type(name_query_limit) is not int or name_query_limit not in (1,2):
            raise ValueError('商品名検索設定が不正です')
        state = SearchState(state_path or Path(output_dir)/'state'/f'{name}_name_search.json', resume=resume, sync=state_sync)
    with client_factory(api_key) as client:
        matching=lookup_by_jan(products,client,start=jan_start,limit=jan_limit)
        jan_tokens = client.total_tokens_consumed
        if enable_name_search:
            names = lookup_by_name(products,matching,client,state,limit=name_limit,
                query_limit=name_query_limit,token_budget=name_token_budget,
                include_no_candidate=name_include_no_candidate,force=force_research,reviews=reviews)
            refresh_approved(names,client)
            merge_approved(matching,names)
        name_tokens = client.total_tokens_consumed-jan_tokens
        analysis=analyze_buybox(matching['asin_products'],client,limit=bb_limit,min_other_share=min_other_share)
        write_excel(path,products,matching,analysis,collector_errors=collector_errors,
                    input_warnings=input_warnings,tokens_consumed=client.total_tokens_consumed,name_matching=names)
        report={**matching['summary'],'manufacturer':str(manufacturer).strip(),
                'jan_errors':len(matching['errors']),'bb_errors':len(analysis['errors']),
                'bb_received':sum(r['BB取得状態']=='RECEIVED' for r in analysis['rows']),
                'tokens_consumed':client.total_tokens_consumed,
                'jan_tokens':jan_tokens,'name_tokens':name_tokens,
                'bb_tokens':client.total_tokens_consumed-jan_tokens-name_tokens,
                'name_errors':len(names['errors']) if names else 0,
                'state_path':str(state.path) if enable_name_search else None,
                'drive_status':'NOT_UPLOADED','local_excel':str(path)}
    report_path=path.with_suffix('.json')
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path,report_path,report
