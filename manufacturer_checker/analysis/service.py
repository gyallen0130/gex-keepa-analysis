from copy import deepcopy
from analysis.buybox import calculate_bb_share
from analysis.candidate_judge import judge_row
from keepa.parser import safe_number, yen_from_keepa
AMAZON_JP_SELLER_ID = 'AN1VRQENFRJN5'

def analyze_buybox(asin_products, client, *, limit=200, min_other_share=0.1, min_coverage=50, now=None):
    if limit is not None and (not isinstance(limit, int) or limit < 0):
        raise ValueError('limitは非負整数またはNone')
    rows = [{**deepcopy(p), **deepcopy(p['amazon'])} for p in asin_products]
    priority = sorted([p for p in rows if p.get('Amazon現在') == 'あり'],
        key=lambda p: (-(safe_number(p.get('Keepa月間販売表示')) or 0), safe_number(p.get('現在ランキング')) or 10**12))
    selected = priority if limit is None else priority[:limit]
    raw, failed, errors = {}, set(), []
    for start in range(0, len(selected), 20):
        asins = [p['asin'] for p in selected[start:start+20]]
        try:
            data = client.keepa_get_with_wait('/product', {'domain':5,'asin':','.join(asins),'buybox':1,'stats':90,'days':90}, len(asins)*3, 'Buy Box取得')
            products = data.get('products')
            if not isinstance(products,list) or any(not isinstance(p,dict) for p in products):
                raise ValueError('応答形式が不正')
            raw.update({p['asin']:p for p in products if p.get('asin') in asins})
        except Exception:
            failed.update(asins);errors.append({'工程':'Buy Box','対象':','.join(asins),'エラー':'取得失敗。クライアントログを確認'})
    amazon_ids = {AMAZON_JP_SELLER_ID}
    for p in raw.values():
        stats = p.get('stats') or {}
        if stats.get('buyBoxIsAmazon') is True and stats.get('buyBoxSellerId'):
            amazon_ids.add(str(stats['buyBoxSellerId']))
    for row in rows:
        p = raw.get(row['asin'])
        row['BB取得状態'] = 'ERROR' if row['asin'] in failed else 'NOT_SCANNED'
        if p is not None:
            row['BB取得状態'] = 'RECEIVED'
            stats = p.get('stats') or {};seller = stats.get('buyBoxSellerId')
            cart = ('Amazon' if stats.get('buyBoxIsAmazon') is True or seller in amazon_ids
                    else 'カートなし' if seller == '-1' else 'セラー不明' if seller in (None,'-2','') else '他セラー')
            row.update({'現在カート':cart,'現在カートSellerID':seller})
            price, shipping = safe_number(stats.get('buyBoxPrice')), safe_number(stats.get('buyBoxShipping'))
            row['現在カート価格'] = yen_from_keepa(price + shipping) if price is not None and price >= 0 and shipping is not None and shipping >= 0 else None
            for days in (30,90):
                bb = calculate_bb_share(p.get('buyBoxSellerIdHistory'),days,amazon_ids,now=now)
                for field,key in [('Amazonカート率%','amazon_pct'),('他セラーカート率%','other_pct'),('他セラーカート日数','other_days'),('カートなし率%','suppressed_pct'),('不明率%','unknown_pct'),('履歴カバー率%','coverage_pct')]:
                    row[f'{days}日_{field}'] = bb[key]
        row['判定'], row['候補'] = judge_row(row,min_other_share=min_other_share,min_coverage=min_coverage)
    return {'rows':rows,'errors':errors,'settings':{'min_other_share':min_other_share,'min_coverage':min_coverage,'bb_limit':limit}}
