"""Headless Chrome UI regression checks; no microphone permission granted."""

import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8788"
root = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        args=["--disable-gpu"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/benchmark.html")
    page.wait_for_function(
        "document.querySelector('#health').textContent.includes('STT:')", timeout=30000
    )
    assert page.locator("#health").inner_text().find("bangla-zipformer") >= 0
    page.locator("#load-script").click()
    page.wait_for_function("document.querySelector('#reference').value.length>100")
    assert not page.locator("#verified").is_checked()
    assert "আসসালামু" in page.locator("#reference").input_value()
    page.locator("#source").select_option("upload")
    assert page.locator("#audio-file").is_visible()
    page.locator("#source").select_option("sample")
    for tab in ["facts", "ledger", "transcript"]:
        # The result tabs are intentionally hidden before there is a result.
        assert page.locator("#result").is_hidden()
    output = root / "data" / "ui-tests"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "benchmark-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
    page.screenshot(path=str(output / "benchmark-mobile.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(base + "/test.html")
    page.wait_for_function(
        "document.querySelector('#status').textContent.includes('PASSED') || document.querySelector('#status').textContent.includes('FAILED')",
        timeout=90000,
    )
    collection = page.locator("#status").inner_text()
    assert collection == "ALL 10 CHECKS PASSED", collection
    assert not errors, errors
    print(
        json.dumps(
            {
                "benchmark_ui": "passed",
                "mobile_overflow": "none",
                "script_reference": "unverified as required",
                "javascript_errors": errors,
                "collection_regression": collection,
                "screenshots": str(output),
            }
        )
    )
    browser.close()
