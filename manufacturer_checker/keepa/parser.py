"""v4.4由来の基本情報パーサー（日本市場専用）。"""
import math
def safe_number(value):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None

def safe_array_get(array, index):
    if not isinstance(array, list) or index >= len(array):
        return None
    value = array[index]
    if value in (-1, -2, None):
        return None
    return value

def yen_from_keepa(value):
    value = safe_number(value)
    if value is None or value < 0:
        return None
    return round(value, 2)  # Amazon.co.jpの最小通貨単位は円（100で割らない）

def product_codes(product):
    values = []
    for key in ("eanList", "upcList"):
        raw = product.get(key) or []
        if isinstance(raw, list):
            values.extend(str(x) for x in raw if x)
    return set(values)

def basic_product_fields(product):
    stats = product.get("stats") or {}
    current = stats.get("current") or []
    avg30 = stats.get("avg30") or []
    avg90 = stats.get("avg90") or []
    amazon_price = yen_from_keepa(safe_array_get(current, 0))
    new_price = yen_from_keepa(safe_array_get(current, 1))

    return {
        "ASIN": product.get("asin"),
        "Keepa商品名": product.get("title"),
        "Keepaブランド": product.get("brand"),
        "Keepaメーカー": product.get("manufacturer"),
        "Amazon現在": ("あり" if amazon_price is not None else
            "不在" if len(current) > 0 and current[0] == -1 else "未確認"),
        "Amazon現在価格": amazon_price,
        "新品現在価格": new_price,
        "現在ランキング": safe_array_get(current, 3),
        "30日平均ランキング": safe_array_get(avg30, 3),
        "90日平均ランキング": safe_array_get(avg90, 3),
        "Keepa月間販売表示": product.get("monthlySold"),
        "Amazon商品ページ": (
            "https://www.amazon.co.jp/dp/" + str(product.get("asin"))
            if product.get("asin") else None
        ),
    }
