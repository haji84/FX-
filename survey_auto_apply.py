#!/usr/bin/env python3
"""アンケート応募フォームを設定ファイルで自動入力・送信するツール。"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

Selector = dict[str, str]
Field = dict[str, Any]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for key in ["url", "fields"]:
        if key not in data:
            raise ValueError(f"設定ファイルに必須キー '{key}' がありません")
    if not isinstance(data["fields"], list) or not data["fields"]:
        raise ValueError("'fields' は1件以上の配列で指定してください")

    return data


def selector_to_by(selector: Selector) -> tuple[str, str]:
    kind = selector.get("by", "css")
    value = selector.get("value", "")
    mapping = {
        "css": By.CSS_SELECTOR,
        "id": By.ID,
        "name": By.NAME,
        "xpath": By.XPATH,
    }
    if kind not in mapping:
        raise ValueError(f"未対応の selector by: {kind}")
    if not value:
        raise ValueError("selector.value が空です")
    return mapping[kind], value


def resolve_value(value: str) -> str:
    if value.startswith("env:"):
        env_key = value.removeprefix("env:")
        return os.getenv(env_key, "")
    return value


def fill_field(driver: webdriver.Chrome, wait: WebDriverWait, field: Field) -> None:
    by, value = selector_to_by(field["selector"])
    element = wait.until(EC.presence_of_element_located((by, value)))
    action = field.get("action", "type")

    if action == "type":
        text = resolve_value(str(field.get("value", "")))
        element.clear()
        element.send_keys(text)
    elif action == "click":
        wait.until(EC.element_to_be_clickable((by, value))).click()
    elif action == "select":
        option_by, option_value = selector_to_by(field["option_selector"])
        option = element.find_element(option_by, option_value)
        option.click()
    else:
        raise ValueError(f"未対応の action: {action}")


def create_driver(headless: bool) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def run(config: dict[str, Any], dry_run: bool, headless: bool, timeout: int) -> None:
    driver = create_driver(headless=headless)
    wait = WebDriverWait(driver, timeout)
    try:
        driver.get(config["url"])

        for idx, field in enumerate(config["fields"], start=1):
            fill_field(driver, wait, field)
            if sleep := float(field.get("sleep", 0)):
                time.sleep(sleep)
            print(f"[{idx}/{len(config['fields'])}] 完了: {field.get('label', 'no-label')}")

        submit = config.get("submit")
        if submit:
            by, value = selector_to_by(submit["selector"])
            if dry_run:
                print("dry-run: 送信しません")
            else:
                wait.until(EC.element_to_be_clickable((by, value))).click()
                print("送信を実行しました")

        if confirm := config.get("confirm_text"):
            try:
                wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), confirm))
                print(f"確認文言を検知: {confirm}")
            except TimeoutException:
                print("確認文言は見つかりませんでした")
    finally:
        driver.quit()


def bootstrap_config(output: Path) -> None:
    print("=== かんたん初期設定 ===")
    url = input("フォームURL: ").strip()
    name_sel = input("氏名のname属性 (例: full_name): ").strip() or "full_name"
    mail_sel = input("メールのname属性 (例: email): ").strip() or "email"
    agree_id = input("同意チェックのid (なければ空): ").strip()
    submit_css = input("送信ボタンCSS (例: button[type='submit']): ").strip() or "button[type='submit']"

    fields: list[dict[str, Any]] = [
        {
            "label": "氏名",
            "selector": {"by": "name", "value": name_sel},
            "action": "type",
            "value": "env:SURVEY_NAME",
        },
        {
            "label": "メール",
            "selector": {"by": "name", "value": mail_sel},
            "action": "type",
            "value": "env:SURVEY_EMAIL",
        },
    ]
    if agree_id:
        fields.append(
            {
                "label": "同意",
                "selector": {"by": "id", "value": agree_id},
                "action": "click",
            }
        )

    config = {
        "url": url,
        "fields": fields,
        "submit": {"selector": {"by": "css", "value": submit_css}},
        "confirm_text": "",
    }

    output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"設定ファイルを作成しました: {output}")
    print("次に実行前に環境変数を設定してください:")
    print("  export SURVEY_NAME='山田 太郎'")
    print("  export SURVEY_EMAIL='taro@example.com'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="アンケート応募フォーム自動化ツール")
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser("init", help="対話形式で設定ファイルを作る")
    init_parser.add_argument("--output", type=Path, default=Path("my_survey.json"), help="出力先")

    run_parser = sub.add_parser("run", help="設定ファイルで実行")
    run_parser.add_argument("config", type=Path, help="設定JSONファイルパス")
    run_parser.add_argument("--no-headless", action="store_true", help="ブラウザを表示")
    run_parser.add_argument("--apply", action="store_true", help="実際に送信")
    run_parser.add_argument("--timeout", type=int, default=10, help="要素待機秒数")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "init":
        bootstrap_config(args.output)
        return

    if args.command == "run":
        config = load_config(args.config)
        run(
            config=config,
            dry_run=not args.apply,
            headless=not args.no_headless,
            timeout=args.timeout,
        )
        return

    print("使い方: init または run を指定してください。例: python survey_auto_apply.py init")


if __name__ == "__main__":
    main()
