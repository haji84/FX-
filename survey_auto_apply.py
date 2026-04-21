#!/usr/bin/env python3
"""アンケート応募フォームを設定ファイルで自動入力・送信するツール。"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


Selector = dict[str, str]
Field = dict[str, Any]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    required = ["url", "fields"]
    for key in required:
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


def fill_field(driver: webdriver.Chrome, wait: WebDriverWait, field: Field) -> None:
    by, value = selector_to_by(field["selector"])
    element = wait.until(EC.presence_of_element_located((by, value)))

    action = field.get("action", "type")

    if action == "type":
        text = field.get("value", "")
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



def run(config: dict[str, Any], dry_run: bool, headless: bool, timeout: int) -> None:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, timeout)

    try:
        driver.get(config["url"])

        for idx, field in enumerate(config["fields"], start=1):
            fill_field(driver, wait, field)
            sleep_sec = float(field.get("sleep", 0))
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            print(f"[{idx}/{len(config['fields'])}] 入力完了: {field.get('label', 'no-label')}")

        submit = config.get("submit")
        if submit:
            by, value = selector_to_by(submit["selector"])
            if dry_run:
                print("dry-run: 送信ボタンは押しません")
            else:
                wait.until(EC.element_to_be_clickable((by, value))).click()
                print("フォーム送信を実行しました")

        if confirm := config.get("confirm_text"):
            try:
                wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), confirm))
                print(f"確認文言を検知: {confirm}")
            except TimeoutException:
                print("確認文言を検知できませんでした")

    finally:
        driver.quit()



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="アンケート応募フォーム自動化ツール")
    parser.add_argument("config", type=Path, help="設定JSONファイルパス")
    parser.add_argument("--no-headless", action="store_true", help="ブラウザを表示して実行")
    parser.add_argument("--apply", action="store_true", help="実際に送信を実行")
    parser.add_argument("--timeout", type=int, default=10, help="要素待機秒数")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run(
        config=config,
        dry_run=not args.apply,
        headless=not args.no_headless,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
