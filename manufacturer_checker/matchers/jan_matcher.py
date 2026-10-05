"""メーカー非依存のJAN照合。単品・セット等の同一性は別工程。"""
from copy import deepcopy
from collections import defaultdict
from core.identifiers import clean_code, normalize_code
from core.deduplicate import group_by_asin
from keepa.parser import product_codes, basic_product_fields

def lookup_by_jan(products, client, *, batch_size=20, start=0, limit=None):
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= 20:
        raise ValueError('batch_sizeは1〜20')
    if not isinstance(start, int) or start < 0 or (limit is not None and (not isinstance(limit, int) or limit < 0)):
        raise ValueError('start/limitは非負整数')
    source = deepcopy(list(products))
    codes = [clean_code(p.get('jan')) for p in source]
    unique = list(dict.fromkeys(c for c in codes if c))
    selected = unique[start:] if limit is None else unique[start:start+limit]
    found = defaultdict(dict)
    attempted, failed, errors = set(), set(), []
    # JAN/UPCの先頭ゼロ差を許容しつつ、複数の入力へ対応付ける。
    for offset in range(0, len(selected), batch_size):
        chunk = selected[offset:offset+batch_size]
        try:
            data = client.keepa_get_with_wait('/product',
                {'domain': 5, 'code': ','.join(chunk), 'code-limit': 10, 'stats': 90, 'history': 0},
                len(chunk)*2, 'JAN照合')
            candidates = data.get('products')
            if not isinstance(candidates, list) or any(not isinstance(p, dict) for p in candidates):
                raise ValueError('products形式が不正')
        except Exception:
            failed.update(chunk)
            errors.append({'codes': chunk, 'reason': 'Keepa取得失敗。通信設定・クライアントログを確認してください'})
            continue
        attempted.update(chunk)
        mapping = defaultdict(list)
        for code in chunk:
            mapping[normalize_code(code)].append(code)
        for candidate in candidates:
            asin = candidate.get('asin')
            if not asin:
                continue
            for code in product_codes(candidate):
                for original in mapping.get(normalize_code(code), []):
                    found[original][asin] = candidate
    matched, unresolved = [], []
    for index, (product, code) in enumerate(zip(source, codes)):
        base = {'source_index': index, 'product': product}
        if found.get(code):
            for asin, candidate in found[code].items():
                matched.append({**base, 'asin': asin, 'amazon': basic_product_fields(candidate),
                    'match_method': 'JAN', 'match_status': 'MATCHED_EXACT',
                    'review_reason': '識別コード一致。単品/セット・容量等の同一性は未検証'})
        else:
            status = ('INSUFFICIENT_DATA' if not code else 'LOOKUP_ERROR' if code in failed
                      else 'NO_CANDIDATE' if code in attempted else 'NOT_SCANNED')
            reason = {'INSUFFICIENT_DATA':'JANなし、または不正形式。型番・商品名照合は未実装',
                'LOOKUP_ERROR':'通信/応答エラー。候補なしとは判定しない',
                'NO_CANDIDATE':'今回のKeepaコード照合で候補なし。Amazon不存在は断定しない',
                'NOT_SCANNED':'今回の開始位置・件数範囲外'}[status]
            unresolved.append({**base, 'match_status': status, 'review_reason': reason})
    grouped = group_by_asin(matched)
    return {'matched': matched, 'asin_products': grouped, 'unresolved': unresolved, 'errors': errors,
        'summary': {'source_products': len(source), 'unique_codes': len(unique),
            'selected_codes': len(selected), 'attempted_codes': len(attempted), 'failed_codes': len(failed),
            'matched_source_products': len({r['source_index'] for r in matched}),
            'matched_rows': len(matched), 'unique_asins': len(grouped), 'unresolved_products': len(unresolved)}}
