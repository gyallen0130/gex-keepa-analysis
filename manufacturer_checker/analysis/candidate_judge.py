"""候補判定。0.1%の元閾値を維持し、設定で変更可能。"""
from keepa.parser import safe_number

def judge_row(row, *, min_other_share=0.1, min_coverage=50.0):
    if not 0 <= min_other_share <= 100 or not 0 <= min_coverage <= 100:
        raise ValueError('閾値は0〜100の百分率')
    if row.get('Amazon現在') == '不在':
        return 'A：Amazon現在不在', '○'
    if row.get('Amazon現在') != 'あり':
        return 'D：Amazon情報未確認', ''
    cart = row.get('現在カート')
    if cart is None:
        return 'D：Buy Box未確認', ''
    if cart == '他セラー':
        return 'B：Amazonあり・現在他セラーカート', '○'
    coverage = safe_number(row.get('90日_履歴カバー率%')) or 0
    # 観測の不足した履歴だけでC候補を出さない。
    if coverage < min_coverage:
        return 'F：Buy Box履歴データ不足', ''
    other = safe_number(row.get('90日_他セラーカート率%'))
    if other is not None and other >= min_other_share:
        return 'C：Amazonあり・他セラーカート実績あり', '○'
    if cart == 'セラー不明' or (safe_number(row.get('90日_不明率%')) or 0) > 0:
        return 'F：Buy Box履歴データ不足', ''
    return 'E：Amazon優勢', ''
