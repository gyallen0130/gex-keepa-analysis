"""ASIN単位に集約し、全メーカー商品との関係を保持する。"""
from copy import deepcopy

def group_by_asin(rows):
    grouped = {}
    for row in rows:
        asin = row.get('asin')
        if not asin:
            continue
        if asin not in grouped:
            grouped[asin] = {'asin': asin, 'amazon': deepcopy(row['amazon']), 'links': []}
        link = {key: deepcopy(row[key]) for key in ('source_index', 'product', 'match_method', 'match_status')}
        if link not in grouped[asin]['links']:
            grouped[asin]['links'].append(link)
    return list(grouped.values())
