# FX-
FXの情報収集、今後の値動き、short、Longのポジションどちらが優位かなどを予測します

## 追加: アンケート応募の自動化（かんたん版）

「初期設定をもっと簡単にしたい」という要望に合わせて、対話形式セットアップを追加しました。

## 最短3ステップ

### 1) インストール

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 対話形式で設定ファイルを作る

```bash
python survey_auto_apply.py init
```

質問に答えるだけで `my_survey.json` が作成されます。

### 3) 値を環境変数に入れて実行

```bash
export SURVEY_NAME='山田 太郎'
export SURVEY_EMAIL='taro@example.com'
python survey_auto_apply.py run my_survey.json
```

入力完了後、送信ボタンを赤枠で強調表示します。  
**送信ボタンは人間が押す前提**です。

```bash
python survey_auto_apply.py run my_survey.json --no-headless --wait-submit
```

## 主な改善点

- ChromeDriver は `webdriver-manager` で自動取得（手動配置不要）
- `init` サブコマンドで設定ファイルを対話作成
- `env:変数名` 形式で、設定ファイルに個人情報を直書きしない運用
- 自動送信は行わず、最終送信は人間が実施する安全運用

## 参考

既存の `sample_survey_config.json` を直接編集して使うことも可能です。

## 注意

- 利用規約や法令に反する自動送信は行わないでください。
- CAPTCHA や 2段階認証があるフォームは別途対応が必要です。
