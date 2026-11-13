"""Real local CPU feature checks. Temporary voice profile is always deleted."""

import json
import sys
import time
from pathlib import Path
import httpx
import numpy as np
import soundfile as sf
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.audio import decode_clip

BASE = "http://127.0.0.1:8787"
client = httpx.Client(base_url=BASE, trust_env=False, timeout=30)


def wait(run_id):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = client.get("/api/runs/" + run_id).json()
        if state["job"]["status"] in ("completed", "partial", "failed"):
            assert state["result"]["status"] == "completed", state["result"].get(
                "error"
            )
            return state["result"]
        time.sleep(1)
    raise RuntimeError("Final analysis timed out")


def main():
    out = ROOT / "data/feature-tests"
    out.mkdir(parents=True, exist_ok=True)
    health = client.get("/api/health").json()
    assert health["streaming_ready"] and health["denoiser_ready"]
    audio, _ = decode_clip(ROOT / "audio/khairul.aac", 0, 10)
    wav = out / "enrollment-smoke.wav"
    sf.write(wav, audio, 16000)
    profile_id = None
    report = {}
    try:
        with wav.open("rb") as handle:
            response = client.post(
                "/api/voices",
                data={
                    "name": "[TEST] single-speaker enrollment",
                    "role": "doctor",
                    "consent": "true",
                },
                files={"audio": (wav.name, handle, "audio/wav")},
            )
        response.raise_for_status()
        profile_id = response.json()["id"]
        assert "embedding" not in response.json()
        assert not list((ROOT / "data/uploads").glob("enrollment-*"))
        report["enrollment"] = (
            "encrypted template created; raw temporary enrollment deleted"
        )
        # A same-source identity smoke test validates plumbing, not identity accuracy.
        with wav.open("rb") as handle:
            response = client.post(
                "/api/runs/upload",
                data={
                    "options": json.dumps(
                        {
                            "max_seconds": 10,
                            "num_speakers": 1,
                            "use_llm": False,
                            "denoise": True,
                            "identify_voices": True,
                        }
                    )
                },
                files={"audio": (wav.name, handle, "audio/wav")},
            )
        response.raise_for_status()
        result = wait(response.json()["id"])
        assert any(
            row.get("profile_id") == profile_id
            for row in result["voice_matches"].values()
        ), result["voice_matches"]
        assert (
            client.get(result["audio"]["enhancement"]["audio_url"]).status_code == 200
        )
        assert result["calls"]["denoise_local_invocations"] == 1
        report["identity_and_denoise_run"] = {
            "id": result["id"],
            "status": result["status"],
            "timings": result["timings"],
            "rss_mb": result["peak_process_rss_mb"],
            "same_source_identity_smoke": "matched",
        }
    finally:
        if profile_id:
            client.delete("/api/voices/" + profile_id).raise_for_status()
        wav.unlink(missing_ok=True)
    assert all(
        row["id"] != profile_id for row in client.get("/api/voices").json()["profiles"]
    )
    report["deletion"] = "temporary signature deleted"
    audio, _ = decode_clip(next((ROOT / "conversation").glob("*.m4a")), 0, 20)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with connect(
        "ws://127.0.0.1:8787/api/live", origin=BASE, open_timeout=15
    ) as socket:
        socket.send(
            json.dumps(
                {
                    "type": "start",
                    "sample_rate": 16000,
                    "consent": True,
                    "options": {"max_seconds": 0, "use_llm": False, "denoise": True},
                }
            )
        )
        assert json.loads(socket.recv())["type"] == "ready"
        text_before_stop = False
        for index in range(0, len(pcm), 1600):
            socket.send(pcm[index : index + 1600].tobytes())
            event = json.loads(socket.recv())
            assert event["type"] == "partial", event
            text_before_stop |= bool(event["text"])
        socket.send(json.dumps({"type": "stop"}))
        final = json.loads(socket.recv())
        assert final["type"] == "final", final
    assert text_before_stop, "No transcript before stop"
    result = wait(final["final_run"]["id"])
    assert result["calls"]["live_stt_decoder_steps"] > 0
    assert result["calls"]["llm_http_attempts"] == 0
    assert result["live_stream"]["received_audio_frames"] == 200
    report["websocket"] = {
        "id": result["id"],
        "partial_before_stop": text_before_stop,
        "streaming": result["live_stream"],
        "final_seconds": result["timings"]["total_seconds"],
        "rss_mb": result["peak_process_rss_mb"],
    }
    (out / "integration.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "enrollment": "passed",
                "same_source_identity": "passed",
                "denoise": "passed",
                "websocket_partial": "passed",
                "final_analysis": "passed",
                "deletion": "passed",
                "result_file": "data/feature-tests/integration.json",
            }
        )
    )


if __name__ == "__main__":
    main()
