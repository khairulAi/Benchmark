"""Stateful local Bengali streaming ASR for bounded PCM WebSocket sessions."""

import gc
import time
import numpy as np
from . import settings as cfg


def streaming_ready():
    return all(
        (cfg.STREAMING_MODEL / name).is_file()
        for name in (
            "encoder.int8.onnx",
            "decoder.onnx",
            "joiner.int8.onnx",
            "tokens.txt",
        )
    )


class LiveRecognizer:
    sample_rate = 16000
    max_samples = 1200 * 16000

    def __init__(self):
        import sherpa_onnx as s

        if not streaming_ready():
            raise RuntimeError("Streaming weights missing; run feature model setup")
        path = cfg.STREAMING_MODEL
        self.model = s.OnlineRecognizer.from_transducer(
            tokens=str(path / "tokens.txt"),
            encoder=str(path / "encoder.int8.onnx"),
            decoder=str(path / "decoder.onnx"),
            joiner=str(path / "joiner.int8.onnx"),
            num_threads=min(2, cfg.THREADS),
            sample_rate=16000,
            feature_dim=80,
            enable_endpoint_detection=False,
            decoding_method="greedy_search",
        )
        self.stream = self.model.create_stream()
        self.samples = 0
        self.frames = 0
        self.decode_steps = 0
        self.started = None
        self.first_text_seconds = None
        self.closed = False

    def _decode(self):
        while self.model.is_ready(self.stream):
            self.model.decode_stream(self.stream)
            self.decode_steps += 1
        text = self.model.get_result(self.stream)
        if text and self.first_text_seconds is None and self.started is not None:
            self.first_text_seconds = round(time.perf_counter() - self.started, 4)
        return text

    def feed(self, pcm):
        if self.closed:
            raise RuntimeError("Streaming session is closed")
        if not pcm or len(pcm) % 2 or len(pcm) > 64000:
            raise ValueError("Send 16-bit mono PCM frames of at most two seconds")
        count = len(pcm) // 2
        if self.samples + count > self.max_samples:
            raise ValueError("Live session limit is 20 minutes")
        if self.started is None:
            self.started = time.perf_counter()
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        self.samples += count
        self.frames += 1
        self.stream.accept_waveform(16000, samples)
        return self._decode()

    def finish(self):
        if self.samples < 16000:
            raise ValueError("Record at least one second before stopping")
        self.stream.accept_waveform(16000, np.zeros(16000, dtype=np.float32))
        self.stream.input_finished()
        return self._decode()

    def summary(self):
        return {
            "transport": "WebSocket",
            "wire_format": "PCM signed 16-bit little-endian mono 16000 Hz",
            "model": "bbbipul/vosk-small-streaming-bn-int8",
            "audio_seconds": self.samples / 16000,
            "received_audio_frames": self.frames,
            "decoder_steps": self.decode_steps,
            "server_ingress_to_first_nonempty_seconds": self.first_text_seconds,
            "server_ingress_to_finish_seconds": round(
                time.perf_counter() - self.started, 4
            )
            if self.started
            else None,
            "http_model_api_calls": 0,
            "note": "Stateful live draft. Speaker/role/fact analysis runs after stop; final ASR is a separate measured pass. Timing excludes microphone startup and is not mouth-to-text latency.",
        }

    def close(self):
        self.closed = True
        self.stream = None
        self.model = None
        gc.collect()
