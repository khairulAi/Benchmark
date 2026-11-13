"""Installed Chrome: real AudioWorklet/WS path using controlled fake mic audio."""

import json
import sys
import uuid
from pathlib import Path
import httpx
import soundfile as sf
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.audio import decode_clip

BASE = "http://127.0.0.1:8787"
client = httpx.Client(base_url=BASE, timeout=20, trust_env=False)
out = ROOT / "data/feature-tests"
out.mkdir(parents=True, exist_ok=True)
mic = out / "chrome-fake-mic.wav"
enrollment = out / "chrome-enrollment.wav"
source, _ = decode_clip(next((ROOT / "conversation").glob("*.m4a")), 0, 20)
sf.write(mic, source, 16000, subtype="PCM_16")
source, _ = decode_clip(ROOT / "audio/khairul.aac", 0, 10)
sf.write(enrollment, source, 16000, subtype="PCM_16")
name = "[TEST] browser-" + uuid.uuid4().hex[:8]
errors = []
report = {}
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True,
            args=[
                "--disable-gpu",
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--use-file-for-fake-audio-capture=" + str(mic),
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, permissions=["microphone"]
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/benchmark.html")
        page.wait_for_function(
            "document.querySelector('#live-status').textContent.includes('Ready')"
        )
        page.locator("#voice-name").fill(name)
        page.locator("#voice-file").set_input_files(str(enrollment))
        page.locator("#voice-consent").check()
        page.locator("#voice-enroll").click()
        row = page.locator(".voice-profile").filter(has_text=name)
        row.wait_for(timeout=30000)
        row.get_by_role("button", name="Delete signature").click()
        row.wait_for(state="detached")
        report["enrollment_and_deletion_ui"] = "passed"
        page.locator("#llm").uncheck()
        page.locator("#denoise").check()
        page.locator("#live-consent").check()
        page.locator("#live-start").click()
        page.wait_for_function(
            "!document.querySelector('#live-stop').disabled", timeout=30000
        )
        page.wait_for_function(
            "document.querySelector('#live-text').value.length > 4", timeout=20000
        )
        page.wait_for_timeout(3000)
        page.locator("#live-stop").click()
        page.wait_for_function(
            "document.querySelector('#metrics').textContent.includes('completed')",
            timeout=60000,
        )
        run_id = page.evaluate("sessionStorage.getItem('meddesk-selected-run')")
        result = client.get("/api/runs/" + run_id).json()["result"]
        assert result["live_stream"]["received_audio_frames"] > 0
        assert result["calls"]["llm_http_attempts"] == 0
        assert result["audio"].get("enhancement")
        assert page.locator("#enhanced-player").is_visible()
        report.update(
            audio_worklet_and_websocket="passed",
            partial_before_stop="passed",
            final_run=run_id,
            audio_seconds=result["audio"]["analyzed_seconds"],
            source="controlled supplied-audio fake microphone; not a real hardware microphone listening test",
        )
        page.screenshot(path=str(out / "features-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
        page.screenshot(path=str(out / "features-mobile.png"), full_page=True)
        page.reload()
        page.wait_for_function(
            "document.querySelector('#metrics').textContent.includes('completed')"
        )
        assert page.locator("#enhanced-player").is_visible()
        assert not errors, errors
        report.update(reload="passed", mobile_overflow="none", javascript_errors=errors)
        browser.close()
finally:
    # Clean up only this test's uniquely named enrollment if any assertion failed.
    for row in client.get("/api/voices").json().get("profiles", []):
        if row["name"] == name:
            client.delete("/api/voices/" + row["id"])
    mic.unlink(missing_ok=True)
    enrollment.unlink(missing_ok=True)
(out / "browser.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
