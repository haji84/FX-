#!/usr/bin/env python3
"""アンケート応募フォームを設定ファイルで自動入力・送信するツール。"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

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
    elif action == "select_by_value":
        Select(element).select_by_value(str(field.get("value", "")))
    elif action == "select_by_text":
        Select(element).select_by_visible_text(str(field.get("value", "")))
    elif action == "select_by_index":
        Select(element).select_by_index(int(field.get("value", 0)))
    elif action == "check":
        clickable = wait.until(EC.element_to_be_clickable((by, value)))
        if not clickable.is_selected():
            clickable.click()
    elif action == "uncheck":
        clickable = wait.until(EC.element_to_be_clickable((by, value)))
        if clickable.is_selected():
            clickable.click()
    else:
        raise ValueError(f"未対応の action: {action}")


def create_driver(headless: bool) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1600,1200")

    return webdriver.Chrome(options=options)


def robust_click(driver: webdriver.Chrome, wait: WebDriverWait, by: str, value: str) -> bool:
    element = wait.until(EC.presence_of_element_located((by, value)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    try:
        wait.until(EC.element_to_be_clickable((by, value))).click()
        return True
    except Exception:
        pass
    try:
        ActionChains(driver).move_to_element(element).pause(0.1).click().perform()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        return False


def click_by_text_candidates(driver: webdriver.Chrome, wait: WebDriverWait, candidates: list[str]) -> bool:
    xpaths = [
        "//button[contains(normalize-space(.), '{text}')]",
        "//a[contains(normalize-space(.), '{text}')]",
        "//input[@type='button' and contains(@value, '{text}')]",
        "//input[@type='submit' and contains(@value, '{text}')]",
        "//img[contains(@alt, '{text}') or contains(@title, '{text}')]",
        "//*[@role='button' and contains(normalize-space(.), '{text}')]",
    ]
    for text in candidates:
        for xp in xpaths:
            query = xp.format(text=text)
            try:
                if robust_click(driver, wait, By.XPATH, query):
                    return True
            except Exception:
                continue
    return False


def answer_survey_first_options(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    # radio: nameごとに先頭を選ぶ
    radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    grouped: defaultdict[str, list[Any]] = defaultdict(list)
    for radio in radios:
        name = radio.get_attribute("name") or f"__noname_{len(grouped)}"
        grouped[name].append(radio)
    for group in grouped.values():
        target = group[0]
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
            if not target.is_selected() and target.is_enabled():
                driver.execute_script("arguments[0].click();", target)
        except Exception:
            continue

    # select: 空でなければ先頭を選ぶ
    selects = driver.find_elements(By.TAG_NAME, "select")
    for elem in selects:
        try:
            select = Select(elem)
            for i, opt in enumerate(select.options):
                if (opt.get_attribute("value") or "").strip():
                    select.select_by_index(i)
                    break
        except Exception:
            continue

    # text/textarea: 空欄にする
    texts = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='tel'], textarea")
    for elem in texts:
        try:
            elem.clear()
        except Exception:
            continue


def run(config: dict[str, Any], headless: bool, timeout: int, wait_submit: bool, auto_survey: bool) -> None:
    driver = create_driver(headless=headless)
    wait = WebDriverWait(driver, timeout)
    try:
        driver.get(config["url"])

        for idx, field in enumerate(config["fields"], start=1):
            fill_field(driver, wait, field)
            if sleep := float(field.get("sleep", 0)):
                time.sleep(sleep)
            print(f"[{idx}/{len(config['fields'])}] 完了: {field.get('label', 'no-label')}")

        if auto_survey:
            for _ in range(8):
                answer_survey_first_options(driver, wait)
                clicked = click_by_text_candidates(
                    driver,
                    wait,
                    ["同意して次に進む", "次に進む", "次へ", "進む", "回答する", "送信", "応募する"],
                )
                if not clicked:
                    break
                time.sleep(1.0)

        submit = config.get("submit")
        if submit:
            by, value = selector_to_by(submit["selector"])
            submit_button = wait.until(EC.element_to_be_clickable((by, value)))
            driver.execute_script(
                "arguments[0].style.outline='3px solid #ff4d4f';"
                "arguments[0].scrollIntoView({behavior:'smooth', block:'center'});",
                submit_button,
            )
            print("入力完了: 送信は人間が押してください（ボタンを赤枠で強調表示しています）")
            if wait_submit:
                input("送信後に Enter を押してください...")

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
    run_parser.add_argument("--wait-submit", action="store_true", help="手動送信後の確認待ちをする")
    run_parser.add_argument("--auto-survey", action="store_true", help="各質問の先頭選択肢を自動選択して進む")
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
            headless=not args.no_headless,
            timeout=args.timeout,
            wait_submit=args.wait_submit,
            auto_survey=args.auto_survey,
        )
        return

    print("使い方: init または run を指定してください。例: python survey_auto_apply.py init")


if __name__ == "__main__":
    main()
