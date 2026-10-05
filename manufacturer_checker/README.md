# メーカー商品調査 共通版

通常はリポジトリトップの「Open In Colab」から実行します。

## 入力と保存

Excel/CSV/TSVの標準見出しは、メーカー・商品名・JANコード・型番・商品コード・容量・サイズ・色・入数・公式URLです。商品名またはJAN列が必要です。他列は任意です。

JANなしの行も保持します。数値セルのJAN、数式、不正形式は「入力確認」タブに注意点を出します。先頭ゼロを保持するため、JANは文字列で保存してください。UTF-8・CP932のCSVに対応します。旧.xlsは.xlsxに保存し直してください。

出力先メーカーは実行時に指定します。複数メーカーが含まれる入力の自動分割は未対応です。

指定Driveの直下にメーカー名フォルダを作成・再利用します。同名フォルダが複数ある場合は停止します。同時実行で同名フォルダが作られる可能性があるため、実行は1つずつ行ってください。保存後はフォルダとファイルサイズを確認します。

## 判定

- A: Amazon価格が明示的に-1（Keepa上で出品価格なし）。
- B: Amazon価格があり、現在他セラーがカートを取得。
- C: 90日履歴カバー率50%以上、他セラーカート率が閾値以上。
- D: Amazon情報またはBB未確認。
- F: 履歴不足・不明データあり。
- E: 上記以外のAmazon優勢判定。

閾値の既定値0.1は0.1%。10なら10%です。履歴率は観測期間を分母とし、カバー率を別列で示します。
JAN一致は識別コードの一致のみで、単品/セット・容量の同一性は未検証です。候補は確認用の一覧です。

JAN不足・候補なし・取得エラー・未調査を区別します。候補なしでもAmazonに存在しないとは断定しません。ASIN単位の集約後も全商品との対応を残します。

## 実装範囲

GEX公式取得、ファイル入力、JAN照合、BB分析、候補判定、Excel出力、Colab、Drive保存を実装。
型番/商品名検索、JAN補完、PDF解析、キャッシュ、他メーカー公式サイト取得、利益/ROI分析は未実装です。

## ローカル開発

```bash
cd manufacturer_checker
pip install -r requirements.txt
python -m unittest discover -s tests -v
# KEEPA_API_KEYを環境変数に設定
python main.py --input 商品一覧.csv --manufacturer メーカー名 --jan-limit 5 --bb-limit 3
```

examples/products.csvは架空サンプルです。API照合には使わないでください。
examples/gex_smoke_products.jsonはGEX公式から取得した5商品のスナップショットです。

仕様資料:
- https://keepa.com/api-docs/statistics-object.html
- https://keepa.com/api-docs/product.html
- https://developers.google.com/workspace/drive/api/guides/folder
