"""Regression tests for disconnected/stalled SSE. No inference or writes to run data."""

import copy
import json
import urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8787"
with urllib.request.urlopen(BASE + "/api/runs") as response:
    jobs = json.load(response)
real = next(
    job for job in jobs if job["status"] == "completed" and not job.get("test_fixture")
)
with urllib.request.urlopen(BASE + "/api/runs/" + real["id"]) as response:
    template = json.load(response)["result"]
outcomes = []
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        args=["--disable-gpu"],
    )
    for mode in ["disconnect", "silent_sse", "poll_network_failure"]:
        context = browser.new_context()
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        fake_id = {"disconnect": "a", "silent_sse": "b", "poll_network_failure": "c"}[
            mode
        ] * 32
        result = copy.deepcopy(template)
        result["id"] = fake_id
        result["status"] = "completed"
        counter = {"get": 0}

        def status(route):
            counter["get"] += 1
            if mode == "poll_network_failure" and counter["get"] == 3:
                route.abort()
                return
            terminal = counter["get"] >= (4 if mode == "poll_network_failure" else 3)
            job = {
                "id": fake_id,
                "status": "completed" if terminal else "diarizing",
                "diarization_progress": 1 if terminal else 0.7,
            }
            route.fulfill(json={"job": job, "result": result if terminal else None})

        page.route("**/api/runs/" + fake_id, status)
        page.route(
            "**/api/runs/" + fake_id + "/reference",
            lambda route: route.fulfill(
                json={
                    "transcript": "",
                    "verified": False,
                    "verification_note": "",
                    "speaker_segments": None,
                    "facts": None,
                }
            ),
        )
        if mode == "disconnect":
            page.route(
                "**/api/runs/" + fake_id + "/events", lambda route: route.abort()
            )
        if mode == "silent_sse":
            page.add_init_script(
                "window.EventSource=class { constructor(url){this.url=url;} close(){} };"
            )
        page.goto(BASE + "/benchmark.html")
        page.wait_for_function(
            "document.querySelector('#health').textContent.includes('STT:')"
        )
        page.locator("#delivery").select_option(
            "poll" if mode == "poll_network_failure" else "sse"
        )
        page.evaluate("(id)=>openRun(id)", fake_id)
        page.wait_for_function(
            "document.querySelector('#metrics').textContent.includes('completed')",
            timeout=20000,
        )
        assert "completed" in page.locator("#progress").inner_text()
        page.reload()
        page.wait_for_function(
            "document.querySelector('#metrics').textContent.includes('completed')",
            timeout=15000,
        )
        assert (
            page.evaluate("sessionStorage.getItem('meddesk-selected-run')") == fake_id
        )
        assert not errors, errors
        outcomes.append(
            {
                "case": mode,
                "result": "PASS",
                "status_requests": counter["get"],
                "reload_recovered": True,
            }
        )
        context.close()
    browser.close()
print(json.dumps(outcomes))
