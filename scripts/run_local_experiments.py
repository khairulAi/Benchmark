"""Small real local-only chunk/noise smoke runs; no provider requests."""

import json
import argparse
import time
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8787")
parser.add_argument("--profile", default="zipformer")
args = parser.parse_args()
client = httpx.Client(
    base_url=args.base,
    timeout=20,
    trust_env=False,
    limits=httpx.Limits(keepalive_expiry=1),
)
report = []


def wait_idle():
    deadline = time.monotonic() + 1200
    while client.get("/api/health").json()["active_run"]:
        if time.monotonic() > deadline:
            raise RuntimeError("Timed out waiting for active run")
        time.sleep(5)


for name, strategy, snr in [
    ("chunks_clean", "chunks", None),
    ("batch_noise_20db", "batch", 20),
]:
    wait_idle()
    options = {
        "max_seconds": 30,
        "offset_seconds": 0,
        "num_speakers": 2,
        "strategy": strategy,
        "chunk_seconds": 15,
        "noise_snr_db": snr,
        "use_llm": False,
        "remote_permission": False,
        "stt_profile": args.profile,
    }
    response = client.post("/api/runs/sample", json=options)
    response.raise_for_status()
    run_id = response.json()["id"]
    print(name, run_id, flush=True)
    with client.stream("GET", f"/api/runs/{run_id}/events") as events:
        assert events.status_code == 200
        assert "text/event-stream" in events.headers["content-type"]
        first = next(line for line in events.iter_lines() if line.startswith("data:"))
        assert json.loads(first[5:])["id"] == run_id
    deadline = time.monotonic() + 600
    while True:
        state = client.get("/api/runs/" + run_id).json()
        if state["job"]["status"] in ["completed", "partial", "failed", "interrupted"]:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Experiment timed out")
        time.sleep(3)
    result = state["result"]
    assert result["status"] == "completed", result.get("error")
    assert result["calls"]["llm_http_attempts"] == 0
    if args.profile in ("zipformer", "indicconformer"):
        calls = [entry for entry in result["ledger"] if entry["stage"] == "stt"]
        assert len(calls) >= 2
        assert all(call["audio_seconds"] <= 15 for call in calls)
        assert abs(sum(call["audio_seconds"] for call in calls) - 30) < 0.001
    else:
        expected = 2 if strategy == "chunks" else 1
        assert result["calls"]["stt_local_invocations"] == expected
    report.append(
        {
            "name": name,
            "id": run_id,
            "status": result["status"],
            "calls": result["calls"],
            "timings": result["timings"],
            "rss_mb": result["peak_process_rss_mb"],
            "audio_noise": result["audio"].get("noise"),
            "status_transports": ["SSE initial event", "HTTP polling"],
        }
    )
(root / "data/local-experiment-summary.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report), flush=True)
