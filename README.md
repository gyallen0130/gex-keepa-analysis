# manufacturer-keepa-analysis

GEXを含む各メーカーの商品一覧から、Amazonの商品ページとBuy Boxの状況を調べるツールです。

## Colabで実行

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gyallen0130/manufacturer-keepa-analysis/blob/main/notebooks/manufacturer_checker.ipynb)

上のボタンを押し、Notebookの①〜⑥を順番に実行してください。ZIPのアップロードは不要です。①が実行時のGitHubコードを取得します。初期設定はGEXの5件試運転です。

1. ① プログラムを取得
2. ② 調査方法・メーカー名・件数を設定
3. ③ Google Drive認証と保存先確認
4. ④ GEX公式またはメーカーの商品一覧から入力を準備
5. ⑤ Keepaキーを入力して照合・分析・Excelを作成
6. ⑥ メーカー別フォルダへ保存

Keepaの有料API契約が必要です。照合でAPIトークンを消費します。JANに複数ASINが該当すると、JAN件数以上のトークンを消費する場合があります。

### 初回設定

Colabの左側の鍵マーク（シークレット）に設定し、このNotebookからのアクセスを許可すると、次回以降の入力を省略できます。

| 名前 | 値 |
|---|---|
| `KEEPA_API_KEY` | Keepa APIキー |
| `DRIVE_PARENT_FOLDER_ID` | 保存先の親フォルダURLまたはフォルダID |

未設定の場合も、③と⑤の入力欄から実行できます。認証には指定フォルダに書き込めるGoogleアカウントを使ってください。

保存先は **親フォルダ → メーカー名 → 日付・時刻付きExcel**。メーカー名フォルダがあれば再利用し、なければ作成します。既存結果は上書きしません。保存だけ失敗した場合は⑥だけ再実行できます。

### 商品取得方法

- **GEX 5件の試運転**: 全巡回をせず、限定した公式商品で動作確認。
- **GEX公式 全商品**: 公式サイトを巡回して商品マスタを作成。その後JAN_LIMITまで照合。
- **Excel/CSV/JSONの商品一覧**: メーカー・卸の.xlsx/.csv/.tsv、または共通形式JSONをアップロード。

JAN_LIMITは0で全件。BB_LIMITは0でBB取得を省略。初期値はJAN 5件・BB 3件です。
商品一覧はメーカーごとに入力し、MANUFACTURERに保存先のメーカー名を指定してください。

## 共通版の仕様と検証

Pythonコードは[`manufacturer_checker/`](manufacturer_checker/)にあります。
[入力・判定の詳細](manufacturer_checker/README.md)を参照してください。

日本向け価格は円単位です。旧v4.4にあった100分の1変換を共通版で修正しています。ルートの既存GEX専用スクリプトは保管用として変更していません。

GEX公式の5件実取得を確認済み。Keepa実API、Colabでの認証、Drive実アップロードは利用環境での確認が必要です。単体テストは模擬レスポンスを使用しています。
