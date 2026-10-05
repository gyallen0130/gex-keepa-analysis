"""少数JANによる実接続確認。GEX全サイト巡回は行わない。"""
import json
from collections import deque
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collectors import gex
from core.identifiers import clean_code
from keepa.client import KeepaClient
from matchers.jan_matcher import lookup_by_jan
from analysis.service import analyze_buybox
from output.excel_writer import write_excel


def collect_gex_sample(limit=5, max_list_pages=8, max_detail_pages=15):
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise ValueError('試運転は1〜10 JAN')
    root = gex.OFFICIAL_ROOTS['アクアリウム']
    # 確認用はバクテリア関連カテゴリから開始し、大分類の巡回を省く。
    sample_root = root + '?m=ProductList&cid=362'
    queue, lists, details, codes, products, errors = deque([sample_root]), set(), set(), set(), [], []
    while queue and len(lists) < max_list_pages and len(details) < max_detail_pages and len(products) < limit:
        url = queue.popleft()
        if url in lists:
            continue
        lists.add(url)
        try:
            soup = BeautifulSoup(gex.request_html(url, retry=1), 'html.parser')
        except Exception:
            errors.append({'工程':'一覧取得', 'URL':url, '理由':'取得失敗'})
            continue
        for a in soup.select('a[href]'):
            target = gex.canonicalize_url(urljoin(url,a.get('href')))
            if gex.is_list_url(target,root) and target not in lists and target not in queue:
                queue.append(target)
            elif gex.is_detail_url(target,root) and target not in details:
                if len(details) >= max_detail_pages:
                    break
                details.add(target)
                try:
                    rows = gex.parse_official_product('アクアリウム',target)
                except Exception:
                    errors.append({'工程':'商品取得','URL':target,'理由':'取得失敗'})
                    continue
                for row in rows:
                    p = gex.to_common_product(row)
                    code = clean_code(p.get('jan'))
                    if code and code not in codes:
                        codes.add(code)
                        products.append(p)
                        if len(products) >= limit:
                            break
                if len(products) >= limit:
                    break
    return {'products':products,'errors':errors,'list_pages':len(lists),'detail_pages':len(details)}


def run_local_check(products, api_key, *, bb_limit=3, output_dir='results', client_factory=KeepaClient, collector_errors=()):
    """ローカル保存まで実行。Driveアップロードは別セルで再試行可能。"""
    if not products or len(products) > 10:
        raise ValueError('試運転の商品数は1〜10件にしてください')
    if not isinstance(bb_limit,int) or not 0 <= bb_limit <= 5:
        raise ValueError('試運転のBB取得は0〜5件')
    out = Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    stamp = datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S_%f')
    path = out / f'GEX_{stamp}_試運転.xlsx'
    with client_factory(api_key) as client:
        matching = lookup_by_jan(products,client,batch_size=5)
        analysis = analyze_buybox(matching['asin_products'],client,limit=bb_limit)
        write_excel(path,products,matching,analysis,collector_errors=collector_errors,
                    tokens_consumed=client.total_tokens_consumed)
        report = {'run_type':'live-smoke','source_products':len(products),**matching['summary'],
            'bb_errors':len(analysis['errors']),'bb_received':sum(r['BB取得状態']=='RECEIVED' for r in analysis['rows']),
            'bb_selected_limit':bb_limit,'bb_status':('VERIFIED' if any(r['BB取得状態']=='RECEIVED' for r in analysis['rows']) else 'NOT_VERIFIED'),
            'tokens_consumed':client.total_tokens_consumed,'tokens_left':client.last_tokens_left,
            'jan_errors':len(matching['errors']),'local_excel':str(path),'drive_status':'NOT_UPLOADED',
            'api_status':('ERRORS' if matching['errors'] or analysis['errors'] else 'RESPONDED'),
            'note':'候補0件でもAPI通信が成功している場合があります。BB未取得は検証済みと扱いません。'}
    report_path = out / f'GEX_{stamp}_試運転診断.json'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return path, report_path, report
