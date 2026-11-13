"""Bounded-memory mono decoding. Never materialize hours of audio for a short clip."""

from pathlib import Path
import av
import numpy as np


def add_noise(audio, snr_db, seed=42):
    rng = np.random.default_rng(seed)
    noise = rng.normal(size=len(audio)).astype(np.float32)
    power = float(np.mean(audio**2))
    noise *= np.sqrt(power / (10 ** (snr_db / 10) * float(np.mean(noise**2))))
    mixed = audio + noise
    peak = float(np.max(np.abs(mixed)))
    gain = 1 / max(peak, 1)
    return mixed * gain, {
        "kind": "synthetic white Gaussian",
        "snr_db": snr_db,
        "seed": seed,
        "global_peak_normalization_gain": gain,
        "note": "Not representative of all real clinical noise; no denoising applied.",
    }


def decode_clip(path: Path, offset_seconds: float, max_seconds: int):
    start = int(offset_seconds * 16000)
    limit = int((max_seconds or 1200) * 16000)
    cursor = 0
    chunks = []
    taken = 0
    with av.open(str(path)) as container:
        total = float(container.duration / av.time_base) if container.duration else None
        if total is not None and offset_seconds >= total:
            raise RuntimeError("Clip offset is beyond audio duration")
        if not max_seconds and total is not None and total - offset_seconds > 1200:
            raise RuntimeError("Choose a clip of 20 minutes or less")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

        def take(frame):
            nonlocal cursor, taken
            values = frame.to_ndarray().reshape(-1)
            left = max(0, start - cursor)
            right = min(len(values), start + limit - cursor)
            if right > left:
                piece = values[left:right].astype(np.float32) / 32768
                chunks.append(piece)
                taken += len(piece)
            cursor += len(values)

        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                take(converted)
            if taken >= limit:
                break
        else:
            for converted in resampler.resample(None):
                take(converted)
        if not chunks:
            raise RuntimeError("No audio decoded in the requested clip")
    return np.ascontiguousarray(np.concatenate(chunks)), total
