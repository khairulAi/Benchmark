"""Optional local GTCRN speech enhancement; never overwrite source audio."""

import gc
import time
import numpy as np
from . import settings as cfg
from .core import sha256


def enhance(audio, ledger):
    import sherpa_onnx as s

    if not cfg.DENOISER.is_file():
        raise RuntimeError("GTCRN weights missing; run model setup")
    entry = {"stage": "denoise", "call_kind": "local_inference", "status": "requested"}
    ledger.append(entry)
    started = time.perf_counter()
    model = None
    try:
        config = s.OfflineSpeechDenoiserConfig(
            model=s.OfflineSpeechDenoiserModelConfig(
                gtcrn=s.OfflineSpeechDenoiserGtcrnModelConfig(model=str(cfg.DENOISER)),
                num_threads=min(cfg.THREADS, 2),
                provider="cpu",
            )
        )
        if not config.validate():
            raise RuntimeError("Invalid denoiser configuration")
        model = s.OfflineSpeechDenoiser(config)
        output = model(audio, 16000)
        samples = np.asarray(output.samples, dtype=np.float32)
        if output.sample_rate != 16000 or not np.isfinite(samples).all():
            raise RuntimeError("Invalid denoiser output")
        # The wrapper compensates model padding. Enforce the exact clip timeline.
        samples = np.pad(samples[: len(audio)], (0, max(0, len(audio) - len(samples))))
        entry.update(
            status="completed", model="GTCRN", model_sha256=sha256(cfg.DENOISER)
        )
        return np.ascontiguousarray(samples)
    except Exception:
        entry["status"] = "failed"
        raise
    finally:
        entry["latency_seconds"] = round(time.perf_counter() - started, 3)
        del model
        gc.collect()


def synthetic_metrics(reference, estimate):
    """Same-timeline signal metrics for injected-noise experiments only.

    The original recording is a surrogate clean reference, not studio-clean
    ground truth. No output alignment or model-based quality judge is applied.
    """
    if len(reference) != len(estimate):
        raise ValueError("Signal/reference length mismatch")

    def dot(a, b):
        return float(np.einsum("i,i->", a, b, dtype=np.float64)) / len(a)

    power = dot(reference, reference)
    predicted = dot(estimate, estimate)
    cross = dot(reference, estimate)
    if power <= 1e-12:
        return {"snr_db": None, "si_sdr_db": None}
    error = max(predicted + power - 2 * cross, 1e-12)
    target = cross * cross / power
    residual = max(predicted - target, 1e-12)
    return {
        "snr_db": round(10 * np.log10(power / error), 3),
        "si_sdr_db": round(10 * np.log10(target / residual), 3)
        if target > 1e-12
        else None,
    }
