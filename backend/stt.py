"""CPU-only Bengali recognizers with bounded inputs and acoustic token alignment."""

from __future__ import annotations

import gc
import os
import time
from pathlib import Path

import numpy as np

from . import settings as cfg

# Disable per-thread MKL buffer pools before CTranslate2 is imported.
# See Intel oneMKL's documented MKL_DISABLE_FAST_MM setting.
os.environ.setdefault("MKL_DISABLE_FAST_MM", "1")
SAMPLE_RATE = 16000
ONNX_PROFILES = {"zipformer", "indicconformer"}


def model_files(profile: str, path: Path) -> list[Path]:
    if profile == "zipformer":
        return [
            path / "int8" / name
            for name in ("encoder.onnx", "decoder.onnx", "joiner.onnx")
        ] + [path / "tokens.txt"]
    if profile == "indicconformer":
        return [path / name for name in ("model.int8.onnx", "vocab.txt", "config.json")]
    return [path / "model.bin"]


def model_ready(profile: str, path: Path) -> bool:
    return all(file.is_file() for file in model_files(profile, path))


def bounded_chunks(audio, seconds=15):
    """Partition without dropping samples; prefer a quiet 40 ms boundary near the cap.

    This is an acoustic boundary heuristic, not VAD or noise removal. Every
    selected boundary is recorded in the invocation ledger for reproducibility.
    """
    limit = int(seconds * SAMPLE_RATE)
    offset = 0
    window = 640
    while offset < len(audio):
        end = min(offset + limit, len(audio))
        if end < len(audio):
            candidates = range(
                max(offset + SAMPLE_RATE, end - 2 * SAMPLE_RATE), end, window
            )
            end = min(
                end,
                min(
                    candidates, key=lambda i: float(np.mean(audio[i : i + window] ** 2))
                )
                + window // 2,
            )
        yield offset, audio[offset:end]
        offset = end


def token_words(tokens, timestamps, offset, duration):
    """Group real token emissions into words; never evenly distribute text.

    Emission times are model estimates, not forced alignment. Word ends use the
    last token emission plus one 40 ms frame to avoid assigning silence to words.
    """
    if len(tokens) != len(timestamps):
        raise RuntimeError("ASR token/timestamp count mismatch")
    words = []
    boundary = True
    for token, stamp in zip(tokens, timestamps):
        token = token.replace("▁", " ")
        if token.startswith("<") and token.endswith(">"):
            continue
        stamp = float(np.clip(stamp, 0, duration)) + offset
        end = min(offset + duration, stamp + 0.04)
        if not token.strip():
            boundary = True
            continue
        if boundary or token.startswith(" ") or not words:
            words.append({"start": stamp, "end": end, "word": " " + token.strip()})
        else:
            words[-1]["word"] += token
            words[-1]["end"] = max(words[-1]["end"], end)
        boundary = False
    return words


def load_onnx(profile, path):
    if profile == "zipformer":
        import sherpa_onnx

        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(path / "int8/encoder.onnx"),
            decoder=str(path / "int8/decoder.onnx"),
            joiner=str(path / "int8/joiner.onnx"),
            tokens=str(path / "tokens.txt"),
            num_threads=cfg.THREADS,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="modified_beam_search",
            max_active_paths=4,
        )
    import onnx_asr
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = cfg.THREADS
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    return onnx_asr.load_model(
        "nemo-conformer-ctc",
        path=path,
        quantization="int8",
        sess_options=options,
        providers=["CPUExecutionProvider"],
    ).with_timestamps()


def transcribe_onnx(audio, update, ledger, profile, path, chunk_seconds):
    model = None
    segments = []
    started = time.perf_counter()
    try:
        model = load_onnx(profile, path)
        update(
            "transcribing",
            {"model_load_seconds": round(time.perf_counter() - started, 3)},
        )
        # Both candidates require short inputs even for one uploaded file.
        for index, (offset, chunk) in enumerate(
            bounded_chunks(audio, min(chunk_seconds, 15)), 1
        ):
            call = {
                "stage": "stt",
                "call_kind": "local_decode",
                "chunk": index,
                "start_seconds": offset / SAMPLE_RATE,
                "audio_seconds": len(chunk) / SAMPLE_RATE,
                "status": "requested",
            }
            ledger.append(call)
            tick = time.perf_counter()
            try:
                if profile == "zipformer":
                    stream = model.create_stream()
                    stream.accept_waveform(SAMPLE_RATE, chunk)
                    model.decode_stream(stream)
                    output = stream.result
                else:
                    output = model.recognize(chunk, sample_rate=SAMPLE_RATE)
                words = token_words(
                    output.tokens or [],
                    output.timestamps or [],
                    offset / SAMPLE_RATE,
                    len(chunk) / SAMPLE_RATE,
                )
                if output.text.strip():
                    if not words:
                        raise RuntimeError(
                            "Recognizer returned text without acoustic timestamps"
                        )
                    segments.append(
                        {
                            "start": words[0]["start"],
                            "end": words[-1]["end"],
                            "text": output.text.strip(),
                            "words": words,
                            "alignment": "acoustic token emission; approximate word ends",
                        }
                    )
                call["status"] = "completed"
                update(
                    "transcribing",
                    {
                        "processed_audio_seconds": round(
                            (offset + len(chunk)) / SAMPLE_RATE, 2
                        )
                    },
                )
            except Exception:
                call["status"] = "failed"
                raise
            finally:
                call["latency_seconds"] = round(time.perf_counter() - tick, 3)
    finally:
        del model
        gc.collect()
    return segments


def transcribe_whisper(audio, update, ledger, strategy, chunk_seconds, path):
    from faster_whisper import WhisperModel

    model = None
    segments = []
    started = time.perf_counter()
    try:
        model = WhisperModel(
            str(path),
            device="cpu",
            compute_type="int8",
            cpu_threads=cfg.WHISPER_THREADS,
            num_workers=1,
            local_files_only=True,
        )
        update(
            "transcribing",
            {"model_load_seconds": round(time.perf_counter() - started, 3)},
        )
        chunk_samples = (
            int(chunk_seconds * SAMPLE_RATE) if strategy == "chunks" else len(audio)
        )
        for index, offset in enumerate(range(0, len(audio), chunk_samples), 1):
            call = {
                "stage": "stt",
                "call_kind": "local_transcribe",
                "chunk": index,
                "start_seconds": offset / SAMPLE_RATE,
                "status": "requested",
            }
            ledger.append(call)
            tick = time.perf_counter()
            generator = None
            try:
                generator, _ = model.transcribe(
                    audio[offset : offset + chunk_samples],
                    language="bn",
                    task="transcribe",
                    beam_size=3,
                    without_timestamps=True,
                    word_timestamps=True,
                    vad_filter=True,
                    condition_on_previous_text=False,
                )
                for segment in generator:
                    segments.append(
                        {
                            "start": segment.start + offset / SAMPLE_RATE,
                            "end": segment.end + offset / SAMPLE_RATE,
                            "text": segment.text,
                            "words": [
                                {
                                    "start": word.start + offset / SAMPLE_RATE,
                                    "end": word.end + offset / SAMPLE_RATE,
                                    "word": word.word,
                                    "probability": word.probability,
                                }
                                for word in segment.words or []
                            ],
                        }
                    )
                    update(
                        "transcribing",
                        {
                            "processed_audio_seconds": round(
                                segment.end + offset / SAMPLE_RATE, 2
                            )
                        },
                    )
                call["status"] = "completed"
            except Exception:
                call["status"] = "failed"
                raise
            finally:
                del generator
                call["latency_seconds"] = round(time.perf_counter() - tick, 3)
    finally:
        del model
        gc.collect()
    return segments


def transcribe(
    audio, update, ledger, strategy, chunk_seconds, path, profile="bangla_asr"
):
    if profile in ONNX_PROFILES:
        return transcribe_onnx(audio, update, ledger, profile, path, chunk_seconds)
    return transcribe_whisper(audio, update, ledger, strategy, chunk_seconds, path)
