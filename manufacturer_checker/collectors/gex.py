"""GEX v4.4の巡回・解析処理。import時に取得や入力を行わない。"""
import re
import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import requests
from bs4 import BeautifulSoup
OFFICIAL_ROOTS = {
    "アクアリウム": "https://product.gex-fp.co.jp/fish/",
    "犬猫": "https://product.gex-fp.co.jp/ca/",
    "小動物": "https://product.gex-fp.co.jp/animal/",
    "爬虫類（エキゾテラ）": "https://product.gex-fp.co.jp/exoterra/",
}
OFFICIAL_WORKERS = 4
REQUEST_TIMEOUT = 45
REQUEST_RETRIES = 4
USER_AGENT = (
    "Mozilla/5.0 (compatible; GEXOfficialCatalogResearch/4.4; "
    "+https://product.gex-fp.co.jp/)"
)

_HTTP_LOCAL = threading.local()

def canonicalize_url(url):
    """フラグメントを除き、クエリ順を統一する。"""
    p = urlparse(url)
    query = parse_qs(p.query, keep_blank_values=True)
    flat = []
    for key in sorted(query):
        for value in sorted(query[key]):
            flat.append((key, value))
    return urlunparse((p.scheme, p.netloc, p.path, "", urlencode(flat), ""))

def request_html(url, retry=REQUEST_RETRIES):
    if not hasattr(_HTTP_LOCAL, "session"):
        _HTTP_LOCAL.session = requests.Session()
        _HTTP_LOCAL.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja",
            "Accept-Encoding": "gzip, deflate",
        })
    last_error = None
    for attempt in range(retry):
        try:
            r = _HTTP_LOCAL.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            r.encoding = r.apparent_encoding or r.encoding
            return r.text
        except Exception as e:
            last_error = e
            if attempt < retry - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"公式ページ取得失敗: {url} / {last_error}")

def query_value(url, key):
    values = parse_qs(urlparse(url).query).get(key, [])
    return values[0] if values else None

def is_same_section(url, root_url):
    u = urlparse(url)
    r = urlparse(root_url)
    return (
        u.scheme in ("http", "https")
        and u.netloc == r.netloc
        and u.path.startswith(r.path)
    )

def is_list_url(url, root_url):
    return is_same_section(url, root_url) and query_value(url, "m") == "ProductList"

def is_detail_url(url, root_url):
    return (
        is_same_section(url, root_url)
        and query_value(url, "m") == "ProductListDetail"
        and query_value(url, "id") is not None
    )

def discover_detail_urls(section_name, root_url):
    queue = deque([canonicalize_url(root_url)])
    visited_lists = set()
    detail_urls = set()
    errors = []

    while queue:
        # 現在見つかっている一覧ページをまとめて並列取得する。
        batch = []
        while queue:
            url = queue.popleft()
            if url not in visited_lists:
                visited_lists.add(url)
                batch.append(url)

        with ThreadPoolExecutor(max_workers=OFFICIAL_WORKERS) as executor:
            futures = {executor.submit(request_html, url): url for url in batch}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    html = future.result()
                except Exception as e:
                    errors.append({"区分": section_name, "URL": url, "エラー": str(e)})
                    continue

                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("a[href]"):
                    absolute = canonicalize_url(urljoin(url, a.get("href")))
                    if is_detail_url(absolute, root_url):
                        detail_urls.add(absolute)
                    elif is_list_url(absolute, root_url) and absolute not in visited_lists:
                        queue.append(absolute)

    return sorted(detail_urls), errors, len(visited_lists)

def parse_official_product(section_name, url):
    html = request_html(url)
    soup = BeautifulSoup(html, "html.parser")

    h1 = (
        soup.select_one("h1.c-detail__ttl")
        or soup.select_one("h1.c-detail__ttl__sp")
        or soup.select_one("h1.page-header__title")
    )
    product_name = h1.get_text(" ", strip=True) if h1 else ""
    if not product_name and soup.title:
        product_name = re.sub(
            r"\s*[|｜]\s*ジェックス株式会社\s*$",
            "",
            soup.title.get_text(" ", strip=True),
        ).strip()

    crumbs = []
    crumb = soup.select_one("p.pankuzu")
    if crumb:
        crumbs = [x.strip() for x in crumb.get_text("|", strip=True).split("|") if x.strip()]
        crumbs = [x for x in crumbs if x != "＞"]

    specs = {}
    for tr in soup.select("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if th and td:
            specs[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)

    jan_text = specs.get("JANコード", "")
    jans = sorted(set(re.findall(r"\d{8,14}", jan_text)))
    if not jans:
        page_text = soup.get_text("\n", strip=True)
        match = re.search(r"JANコード\s*([0-9]{8,14})", page_text)
        if match:
            jans = [match.group(1)]

    product_id = query_value(url, "id")
    cid = query_value(url, "cid")
    category_path = " ＞ ".join(crumbs[2:-1]) if len(crumbs) >= 4 else ""

    base = {
        "公式区分": section_name,
        "公式商品名": product_name,
        "公式カテゴリ": category_path,
        "公式商品ID": product_id,
        "公式カテゴリID": cid,
        "商品コード": specs.get("コード"),
        "標準小売価格": specs.get("標準小売価格"),
        "原産国": specs.get("原産国"),
        "公式商品ページ": url,
    }

    if jans:
        return [{**base, "JANコード": jan} for jan in jans]
    return [{**base, "JANコード": None}]


def to_common_product(row):
    """GEX商品コードを型番と決めつけず、メーカー商品コードとして保持。"""
    return dict(manufacturer="GEX", brand="", product_name=row["公式商品名"],
        jan=row.get("JANコード") or "", model_number="",
        manufacturer_code=row.get("商品コード") or "", category=row["公式カテゴリ"],
        capacity="", size="", color="", pack_quantity="",
        official_url=row["公式商品ページ"], source_type="official_web",
        source_url=row["公式商品ページ"], source_section=row["公式区分"],
        official_product_id=row["公式商品ID"], official_category_id=row["公式カテゴリID"],
        suggested_retail_price=row.get("標準小売価格"), country_of_origin=row.get("原産国"))


class GexCollector:
    def __init__(self, roots=None):
        self.roots = dict(OFFICIAL_ROOTS if roots is None else roots)
        self.errors = []
        self.visited_list_count = 0

    def collect(self):
        self.errors = []
        self.visited_list_count = 0
        products = []
        seen = set()
        for section, root_url in self.roots.items():
            urls, errors, visited = discover_detail_urls(section, root_url)
            self.errors.extend(errors)
            self.visited_list_count += visited
            with ThreadPoolExecutor(max_workers=OFFICIAL_WORKERS) as executor:
                futures = {executor.submit(parse_official_product, section, url): url for url in urls}
                for future in as_completed(futures):
                    try:
                        for row in future.result():
                            product = to_common_product(row)
                            key = (product["official_url"], product["jan"])
                            if key not in seen:
                                seen.add(key)
                                products.append(product)
                    except Exception as error:
                        self.errors.append({"区分": section, "URL": futures[future], "エラー": str(error)})
        return sorted(products, key=lambda p: (p["source_section"], p["official_url"], p["jan"]))
