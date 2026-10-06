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

## v1.1：JANがない商品を商品名から検索

Colabの②で `ENABLE_NAME_SEARCH=True` にすると、JANなし／不正形式の商品をブランド・商品名・容量でKeepa検索します。JAN照合0件も対象にする場合だけ `NAME_INCLUDE_NO_CANDIDATE=True` にします。JAN未調査や通信失敗は商品名検索で迂回しません。

初回は `NAME_SEARCH_LIMIT=20`、`NAME_QUERY_LIMIT=2`、`NAME_TOKEN_BUDGET=400` を推奨します。JAN_LIMIT・BB_LIMITとは独立した上限で、商品名検索の件数・予算で0は無制限です。基本検索は1回10トークンの目安、後続の商品取得・BB分析・再送は追加消費します。商品名検索は候補の発見であり、Amazonの商品を網羅する保証はありません。

1. 商品一覧をアップロードして実行します。日仏商事の調査にはJANなしを含む全532件CSVを使います。
2. 結果の「商品名検索候補」「確認入力」で、ブランド・容量・味・単品／セットを確認します。
3. 「確認入力」の採用欄を「採用／除外／保留」に編集してExcelを保存します。
4. 次回②で `UPLOAD_REVIEW=True` を選び、④で同じ商品一覧に続けて確認済みExcelをアップロードします。
5. 採用したASINだけが `NAME_REVIEWED` として既存分析へ入り、価格情報を取得し直します。入力規格変更や複数ASINの採用はエラーにして再確認を促します。

未承認の候補はA～F判定・仕入れ候補・BB追加取得に入りません。JAN一致も単品／セットの保証ではない点は従来どおりです。候補側EANを入力JANに書き戻しません。入数が分からない商品は単品と推測せず「要確認」とします。

任意の入力列：検索キーワード、単品容量、販売単位数、味・種類。商品コードは卸の注文番号として扱い、メーカー型番やJANに読み替えません。「1kg×6/ctn」の6は物流ケース入数であり、販売単位数を自動設定しません。

`SAVE_TO_DRIVE=True` の場合は指定親フォルダ／メーカー名／`_state/name_search_v1.json` に検索状態を同期します。`RESUME=True` なら次回は未完了分から再開します。正常な検索結果は7日間再利用し、`FORCE_RESEARCH=True` で再検索できます。JAN検索と価格・BB分析は再実行されます。複数のColabセッションで同じメーカーを同時実行しないでください。

Drive保存OFFでは状態はColab内のみです。セッションを閉じる前に状態をダウンロードしてください。セッションをまたぐ自動復元はDrive保存ONを使います。同期に失敗するとその場で処理を止め、ローカル状態を保持します。API応答直後から保存前に停止した場合は再検索で追加消費することがあります。

CLI例：

```bash
python main.py --input products.csv --manufacturer 日仏商事 --jan-limit 50 --bb-limit 0 --name-search --name-limit 20 --name-token-budget 400
```

次回は同じコマンドで続きを検索し、確認Excelを読み込むには `--review result_reviewed.xlsx` を追加します。`--name-include-no-candidate`、`--force-research`、`--no-resume` も利用できます。

API資料（実装時確認）：https://keepa.com/api-docs/product-search.html 。詳細ページと概要の結果件数表記に差があるため、件数を固定せず返された商品一覧を処理します。
