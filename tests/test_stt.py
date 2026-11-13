"""Regression checks for bounded decoding and speaker-alignment inputs."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from backend.stt import bounded_chunks, token_words, transcribe_whisper


def test_partition_preserves_every_sample_and_enforces_model_limit():
    audio = np.arange(16000 * 49, dtype=np.float32)
    chunks = list(bounded_chunks(audio, 15))
    assert np.array_equal(np.concatenate([chunk for _, chunk in chunks]), audio)
    assert all(0 < len(chunk) <= 15 * 16000 for _, chunk in chunks)
    assert all(
        offset == sum(len(chunk) for _, chunk in chunks[:i])
        for i, (offset, _) in enumerate(chunks)
    )


def test_acoustic_word_alignment_preserves_offsets_and_separate_boundary_tokens():
    words = token_words(["▁জ", "্বর", "▁", "নেই"], [0.1, 0.2, 0.5, 0.6], 10, 1)
    assert [word["word"] for word in words] == [" জ্বর", " নেই"]
    assert words[0]["start"] == pytest.approx(10.1)
    assert words[0]["end"] == pytest.approx(10.24)
    assert words[1]["start"] == pytest.approx(10.6)
    with pytest.raises(RuntimeError):
        token_words(["জ্বর"], [], 0, 1)


def test_lazy_decoder_error_is_a_failed_audited_invocation(monkeypatch, tmp_path):
    class BrokenModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            def fail_during_iteration():
                raise RuntimeError("simulated allocation failure")
                yield

            return fail_during_iteration(), None

    monkeypatch.setitem(
        sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=BrokenModel)
    )
    calls = []
    with pytest.raises(RuntimeError, match="allocation"):
        transcribe_whisper(
            np.zeros(16000, dtype=np.float32),
            lambda *_: None,
            calls,
            "batch",
            15,
            tmp_path,
        )
    assert len(calls) == 1
    assert calls[0]["status"] == "failed"
    assert calls[0]["latency_seconds"] >= 0


def test_onnx_readiness_requires_all_graphs_and_vocabulary(tmp_path):
    from backend.stt import model_files, model_ready

    files = model_files("zipformer", tmp_path)
    for path in files[:-1]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test fixture")
    assert not model_ready("zipformer", tmp_path)
    files[-1].write_text("token 0", encoding="utf-8")
    assert model_ready("zipformer", tmp_path)
