# FX-
FXの情報収集、今後の値動き、short、Longのポジションどちらが優位かなどを予測します

## 追加: アンケート応募の自動化

アンケート応募を自動化できるように、`survey_auto_apply.py` を追加しました。  
Selenium でフォーム要素を順番に入力し、必要に応じて送信まで実行します。

### 1. セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 実行環境に Google Chrome と対応する ChromeDriver が必要です。

### 2. 設定ファイルを作成

`sample_survey_config.json` をコピーし、対象フォームに合わせて編集します。

```bash
cp sample_survey_config.json my_survey.json
```

- `url`: フォームURL
- `fields`: 入力する項目（`type` / `click` / `select`）
- `submit`: 送信ボタン（任意）
- `confirm_text`: 送信後にページ本文に表示される確認文言（任意）

### 3. 実行

まずは送信しない dry-run（デフォルト）で確認:

```bash
python survey_auto_apply.py my_survey.json
```

実際に送信する場合:

```bash
python survey_auto_apply.py my_survey.json --apply
```

ブラウザを表示して確認する場合:

```bash
python survey_auto_apply.py my_survey.json --no-headless
```

## 注意

- 利用規約や法令に反する自動送信は行わないでください。
- 同じフォームへの過剰アクセスは避けてください。
- CAPTCHA や 2段階認証があるフォームは別途対応が必要です。
