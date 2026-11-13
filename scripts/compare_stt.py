"""Compare local recognizers in fresh processes on one fixed, attested reference."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def worker(profile):
    import threading
    import psutil
    from backend import settings
    from backend.audio import decode_clip
    from backend.core import atomic_json, transcript_metrics, sha256
    from backend.stt import transcribe

    work = ROOT / "data/model-comparison"
    reference = json.loads((work / "reference.json").read_text("utf-8"))
    source = next((ROOT / "conversation").glob("*.m4a"))
    audio, _ = decode_clip(source, 0, reference["clip_seconds"])
    calls = []
    peak = [0]
    done = threading.Event()

    def monitor():
        while not done.wait(0.1):
            peak[0] = max(peak[0], psutil.Process().memory_info().rss)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    started = time.perf_counter()
    result = {
        "profile": profile,
        "source_sha256": sha256(source),
        "reference": reference,
        "status": "running",
        "ledger": calls,
        "threads": settings.THREADS,
        "stt_source_sha256": sha256(ROOT / "backend/stt.py"),
        "chunk_policy": "ONNX: <=15s at quiet boundaries; Whisper: fixed 15s, VAD. Architecture-appropriate pipeline comparison, not isolated architecture ablation.",
        "model_manifest": json.loads(
            (
                (settings.STT_PROFILES[profile][1] / "manifest.json")
                if (settings.STT_PROFILES[profile][1] / "manifest.json").exists()
                else settings.MODELS / "manifest.json"
            ).read_text("utf-8")
        ),
    }
    try:
        segments = transcribe(
            audio,
            lambda *_: None,
            calls,
            "chunks",
            15,
            settings.STT_PROFILES[profile][1],
            profile,
        )
        result["segments"] = segments
        result["transcript"] = " ".join(s["text"] for s in segments)
        result["metrics"] = transcript_metrics(
            reference["transcript"], result["transcript"]
        )
        result["status"] = "completed"
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)
    finally:
        done.set()
        thread.join()
        result["seconds"] = round(time.perf_counter() - started, 3)
        result["peak_rss_mb"] = round(peak[0] / 1024**2, 1)
        atomic_json(work / (profile + ".json"), result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("profile", "status", "seconds", "peak_rss_mb")
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["zipformer", "indicconformer", "vivasoft", "bangla_asr"],
    )
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    from backend.core import atomic_json, docx_script, sha256

    script = next((ROOT / "conversation").glob("*.docx"))
    utterances = docx_script(script)
    # Fixed before running any of these model comparisons. User permits a
    # complete nearby boundary; 113s precedes the next doctor's wound question.
    end = (
        next(i for i, u in enumerate(utterances) if u["text"].startswith("পায়ের পাতায়"))
        + 1
    )
    reference = {
        "clip_seconds": 113,
        "transcript": " ".join(u["text"] for u in utterances[:end]),
        "script_sha256": sha256(script),
        "last_utterance": utterances[end - 1]["text"],
        "provenance": "User attests first two minutes checked; DOCX subset. 113s boundary estimated from previous transcript timestamps, not independently listened to by evaluator. Provisional until exact clip boundary and verbatim text confirmed.",
        "purpose": "Development comparison on one conversation, not held-out clinical validation",
    }
    work = ROOT / "data/model-comparison"
    atomic_json(work / "reference.json", reference)
    for profile in args.profiles:
        print("Starting", profile, flush=True)
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker", profile],
                cwd=ROOT,
                timeout=1200,
            )
            if process.returncode:
                print("Worker failed", profile, process.returncode, flush=True)
        except subprocess.TimeoutExpired:
            print("Worker timed out", profile, flush=True)
    rows = []
    for profile in args.profiles:
        path = work / (profile + ".json")
        if path.exists():
            result = json.loads(path.read_text("utf-8"))
            rows.append(
                {
                    "profile": profile,
                    "status": result["status"],
                    "seconds": result["seconds"],
                    "peak_rss_mb": result["peak_rss_mb"],
                    "wer": result.get("metrics", {}).get("wer", {}).get("rate"),
                    "cer": result.get("metrics", {}).get("cer", {}).get("rate"),
                }
            )
    atomic_json(work / "summary.json", {"reference": reference, "results": rows})
    print(json.dumps(rows), flush=True)


if __name__ == "__main__":
    main()
