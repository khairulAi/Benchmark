"""Exercise real run rendering, reference persistence and downloadable reports."""

import json
import sys
import uuid
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
parent_id = json.loads((root / "data/latest-validation-run.json").read_text())["id"]
parent = root / "data/runs" / parent_id
run_id = uuid.uuid4().hex
fixture = root / "data/runs" / run_id
fixture.mkdir()
result = json.loads((parent / "result.json").read_text("utf-8"))
result.update(
    id=run_id,
    execution_kind="ui_test_fixture",
    parent_run=parent_id,
    cost_usd=None,
    ledger=[],
    metrics=None,
)
result["calls"] = {
    "stt_local_invocations": 0,
    "llm_http_attempts": 0,
    "diarization_local_invocations": 0,
    "note": "UI test copy only; no inference performed.",
}
(fixture / "result.json").write_text(
    json.dumps(result, ensure_ascii=False), encoding="utf-8"
)
(fixture / "job.json").write_text(
    json.dumps(
        {
            "id": run_id,
            "status": result["status"],
            "source_name": "[TEST] UI fixture",
            "test_fixture": True,
            "created_at": time.time(),
            "options": result["options"],
        }
    ),
    encoding="utf-8",
)
if (parent / "source.json").exists():
    (fixture / "source.json").write_bytes((parent / "source.json").read_bytes())
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        args=["--disable-gpu"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + "/benchmark.html?show_tests=1")
    page.get_by_role("button", name=run_id[:8], exact=False).click()
    page.locator(".utterance").first.wait_for(timeout=30000)
    assert page.locator("#metrics").inner_text().find("completed") >= 0
    page.locator("[data-tab=facts]").click()
    assert page.locator("#facts").is_visible()
    page.locator("[data-tab=ledger]").click()
    assert "stt_local_invocations" in page.locator("#ledger").inner_text()
    page.locator("#reference").fill("অসম্পূর্ণ পরীক্ষামূলক খসড়া — verified নয়।")
    assert not page.locator("#verified").is_checked()
    page.locator("#score").click()
    page.wait_for_function(
        "document.querySelector('#scores').textContent.includes('unverified')"
    )
    # Persist only an unverified draft; never claim human verification in automation.
    page.reload()
    page.get_by_role("button", name=run_id[:8], exact=False).click()
    page.wait_for_function(
        "document.querySelector('#reference').value.includes('অসম্পূর্ণ')"
    )
    assert not page.locator("#verified").is_checked()
    with page.expect_download() as info:
        page.locator("#download").click()
    download = info.value
    report = json.loads(Path(download.path()).read_text("utf-8"))
    assert report["id"] == run_id
    assert report["source_audio_embedded"] is False
    assert report["evaluation_reference"]["verified"] is False
    assert report["metrics"]["status"] == "unverified"
    page.locator("[data-tab=transcript]").click()
    page.get_by_role("button", name="▶ Listen to this utterance").first.click()
    page.wait_for_function("document.querySelector('#source-audio').readyState>=1")
    output = root / "data/ui-tests"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "benchmark-real-result.png"), full_page=True)
    assert not errors, errors
    print(
        json.dumps(
            {
                "real_result_rendering": "passed",
                "tabs": "passed",
                "unverified_reference_persists": "passed",
                "report_download": "passed",
                "source_playback_metadata": "passed",
                "javascript_errors": errors,
            }
        )
    )
    browser.close()
