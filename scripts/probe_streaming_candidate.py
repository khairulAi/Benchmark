"""Local-only feasibility check of a small Bengali streaming transducer."""

import json
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import psutil
    import sherpa_onnx
    from backend import settings
    from backend.audio import decode_clip
    from backend.core import atomic_json, transcript_metrics

    reference = json.loads(
        (ROOT / "data/model-comparison/reference.json").read_text("utf-8")
    )
    audio, _ = decode_clip(
        next((ROOT / "conversation").glob("*.m4a")), 0, reference["clip_seconds"]
    )
    path = settings.MODELS / "vosk-small-streaming-bn-int8"
    peak = [psutil.Process().memory_info().rss]
    done = threading.Event()

    def monitor():
        while not done.wait(0.1):
            peak[0] = max(peak[0], psutil.Process().memory_info().rss)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    tick = time.perf_counter()
    model = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(path / "tokens.txt"),
        encoder=str(path / "encoder.int8.onnx"),
        decoder=str(path / "decoder.onnx"),
        joiner=str(path / "joiner.int8.onnx"),
        num_threads=2,
        sample_rate=16000,
        feature_dim=80,
        enable_endpoint_detection=False,
        decoding_method="greedy_search",
    )
    stream = model.create_stream()
    for offset in range(0, len(audio), 1600):
        stream.accept_waveform(16000, audio[offset : offset + 1600])
        while model.is_ready(stream):
            model.decode_stream(stream)
    stream.accept_waveform(16000, np.zeros(16000, dtype=np.float32))
    stream.input_finished()
    while model.is_ready(stream):
        model.decode_stream(stream)
    output = model.get_result(stream)
    done.set()
    thread.join()
    result = {
        "profile": "vosk_streaming",
        "model": "bbbipul/vosk-small-streaming-bn-int8",
        "revision": "19d0fc5890941faab7b080a26b6821f3d456fbf1",
        "status": "completed",
        "text": output,
        "seconds": round(time.perf_counter() - tick, 3),
        "peak_rss_mb": round(peak[0] / 1024**2, 1),
        "metrics": transcript_metrics(reference["transcript"], output),
        "threads": 2,
        "note": "Stateful model fed a prerecorded file; not a live WebSocket test. Same provisional reference as other candidates.",
    }
    atomic_json(ROOT / "data/model-comparison/vosk_streaming.json", result)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("profile", "seconds", "peak_rss_mb", "metrics")
            }
        )
    )


if __name__ == "__main__":
    main()
