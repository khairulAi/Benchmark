from backend.schemas import Options, Reference, TimedReference
import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend import jobs as server
from backend.app import app
from backend.core import (
    Extraction,
    bind_words,
    edit_counts,
    normalize,
    transcript_metrics,
    validate_evidence,
)
from backend.evaluation import score


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.cfg, "DATA", tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "uploads").mkdir()
    monkeypatch.setattr(server, "active", None)
    return TestClient(app)


def test_bengali_normalization():
    assert normalize("জ্বর ৩ দিন।") == "জ্বর 3 দিন"
    assert transcript_metrics("জ্বর ৩ দিন।", "জ্বর 3 দিন")["wer"]["rate"] == 0


def test_edit_counts_with_insert_delete_substitute():
    assert edit_counts(["a", "b"], ["a", "c"])["substitutions"] == 1
    assert edit_counts(["a", "b"], ["a"])["deletions"] == 1
    assert edit_counts(["a"], ["a", "b"])["insertions"] == 1
    assert edit_counts([], ["a"])["rate"] is None


def test_speaker_alignment_and_overlap():
    words = [
        {
            "start": 0,
            "end": 1,
            "text": "জ্বর",
            "words": [{"start": 0, "end": 1, "word": "জ্বর"}],
        }
    ]
    assert (
        bind_words(words, [{"start": 0, "end": 1, "speaker": "A"}])[0]["speaker"] == "A"
    )
    assert (
        bind_words(
            words,
            [
                {"start": 0, "end": 1, "speaker": "A"},
                {"start": 0, "end": 1, "speaker": "B"},
            ],
        )[0]["speaker"]
        == "unknown"
    )
    assert bind_words(words, [])[0]["speaker"] == "unknown"


def test_evidence_filter_rejects_hallucinations():
    extraction = Extraction.model_validate(
        {
            "roles": [{"speaker": "A", "role": "patient", "evidence_ids": ["wrong"]}],
            "facts": [
                {
                    "category": "symptom",
                    "value": "জ্বর",
                    "polarity": "present",
                    "evidence_id": "u1",
                    "quote": "জ্বর নেই",
                },
                {
                    "category": "symptom",
                    "value": "ব্যথা",
                    "polarity": "present",
                    "evidence_id": "u1",
                    "quote": "ব্যথা আছে",
                },
            ],
            "summary_bn": "",
            "warnings": [],
        }
    )
    result, warnings = validate_evidence(
        extraction, [{"id": "u1", "speaker": "A", "text": "আমার জ্বর নেই"}]
    )
    assert len(result["facts"]) == 1
    assert result["roles"][0]["role"] == "unknown"
    assert warnings


def result_fixture():
    return {
        "audio": {"analyzed_seconds": 2},
        "asr_segments": [{"text": "জ্বর নেই"}],
        "speaker_segments": [
            {"start": 0, "end": 1, "speaker": "X"},
            {"start": 1, "end": 2, "speaker": "Y"},
        ],
        "transcript": [
            {"start": 0, "end": 1, "role": "doctor"},
            {"start": 1, "end": 2, "role": "patient"},
        ],
        "extraction": {"facts": []},
    }


def test_unverified_reference_cannot_produce_accuracy():
    assert score(result_fixture(), {"verified": False})["status"] == "unverified"


def test_der_maps_permuted_speakers_and_role_accuracy():
    ref = {
        "verified": True,
        "transcript": "জ্বর নেই",
        "speaker_segments": [
            {"start": 0, "end": 1, "speaker": "D", "role": "doctor"},
            {"start": 1, "end": 2, "speaker": "P", "role": "patient"},
        ],
        "facts": [],
    }
    metrics = score(result_fixture(), ref)
    assert metrics["der"]["rate"] == 0
    assert metrics["role_accuracy"]["rate"] == 1
    assert metrics["transcription"]["wer"]["rate"] == 0
    assert metrics["fact_f1"]["f1"] == 1


def test_der_missed_speech():
    result = result_fixture()
    result["speaker_segments"] = []
    ref = {
        "verified": True,
        "transcript": "জ্বর নেই",
        "speaker_segments": [{"start": 0, "end": 2, "speaker": "A"}],
    }
    assert score(result, ref)["der"]["rate"] == 1


def test_health_contains_no_key(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "LLM_API_KEY" not in response.text
    assert "llm_key" not in response.json()


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/.git/config",
        "/data/runs/x/result.json",
        "/models/manifest.json",
        "/backend/settings.py",
        "/audio/../.env",
    ],
)
def test_static_private_files_blocked(client, path):
    assert client.get(path).status_code == 404


def test_remote_permission_required(client):
    assert (
        client.post(
            "/api/runs/sample", json={"use_llm": True, "remote_permission": False}
        ).status_code
        == 422
    )


def test_cross_origin_mutation_blocked(client):
    assert (
        client.post(
            "/api/runs/sample", headers={"Origin": "https://untrusted.example"}, json={}
        ).status_code
        == 403
    )


def test_bad_host_rejected(client):
    assert (
        client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    )


def test_reference_schema_rejects_bad_timestamps():
    with pytest.raises(ValueError):
        TimedReference(start=2, end=1, speaker="A")
    with pytest.raises(ValueError):
        Reference(transcript="", verified=True)


def test_empty_and_bad_uploads(client):
    options = json.dumps({"use_llm": False})
    assert (
        client.post(
            "/api/runs/upload",
            data={"options": options},
            files={"audio": ("x.wav", b"")},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/runs/upload",
            data={"options": options},
            files={"audio": ("x.exe", b"bad")},
        ).status_code
        == 415
    )


def test_oversized_upload_rejected_before_parsing(client):
    assert (
        client.post(
            "/api/runs/upload",
            headers={"Content-Length": str(60 * 1024 * 1024)},
            content=b"",
        ).status_code
        == 413
    )


def test_run_path_validation(client):
    assert client.get("/api/runs/not-a-run").status_code == 404


def test_sample_is_unverified(client):
    data = client.get("/api/sample").json()
    assert data["verified"] is False
    assert "LLM_API_KEY" not in str(data)


def test_configured_cost_unknown_not_zero(monkeypatch):
    monkeypatch.delenv("TEST_PRICE", raising=False)
    assert server.cfg.configured_price("TEST_PRICE") is None


def test_audio_clip_is_bounded_and_offsets_work(tmp_path):
    import wave
    from backend.audio import decode_clip

    path = tmp_path / "test.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(np.full(16000 * 3, 1000, dtype="<i2").tobytes())
    audio, total = decode_clip(path, 1, 1)
    assert len(audio) == 16000
    assert total == 3
    assert np.allclose(audio, 1000 / 32768)
    with pytest.raises(RuntimeError):
        decode_clip(path, 10, 1)


def test_llm_token_cost_evidence_and_call_count(monkeypatch):
    from backend import llm

    monkeypatch.setattr(llm.cfg, "LLM_KEY", "test-key-not-a-real-secret")
    monkeypatch.setattr(llm.cfg, "LLM_BASE", "https://provider.example/v1")
    monkeypatch.setattr(llm.cfg, "LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_INPUT_USD_PER_MILLION", "2")
    monkeypatch.setenv("LLM_OUTPUT_USD_PER_MILLION", "4")
    payload = {
        "roles": [{"speaker": "A", "role": "patient", "evidence_ids": ["u1"]}],
        "facts": [
            {
                "category": "symptom",
                "value": "জ্বর",
                "polarity": "absent",
                "evidence_id": "u1",
                "quote": "জ্বর নেই",
            }
        ],
        "summary_bn": "",
        "warnings": [],
    }

    class Response:
        status_code = 200

        def json(self):
            return {
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "model": "test-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(payload)},
                    }
                ],
            }

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            assert url == "https://provider.example/v1/chat/completions"
            assert "reference" not in json["messages"][1]["content"]
            return Response()

    monkeypatch.setattr(llm.httpx, "Client", Client)
    ledger = []
    result, warnings = llm.extract(
        [{"id": "u1", "speaker": "A", "text": "আমার জ্বর নেই"}], ledger
    )
    assert len(ledger) == 1 and ledger[0]["status"] == "completed"
    assert ledger[0]["cost_usd"] == pytest.approx(0.00004)
    assert result["facts"][0]["polarity"] == "absent"
    assert not warnings


def test_llm_http_failure_is_counted_without_retry(monkeypatch):
    from backend import llm

    monkeypatch.setattr(llm.cfg, "LLM_KEY", "test-key")
    monkeypatch.setattr(llm.cfg, "LLM_BASE", "https://provider.example/v1")
    monkeypatch.setattr(llm.cfg, "LLM_MODEL", "test-model")

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return type("Response", (), {"status_code": 401})()

    monkeypatch.setattr(llm.httpx, "Client", Client)
    ledger = []
    with pytest.raises(RuntimeError, match="HTTP 401"):
        llm.extract([], ledger)
    assert len(ledger) == 1 and ledger[0]["status"] == "failed"


def test_mixed_role_evidence_keeps_only_valid_support():
    result, warnings = validate_evidence(
        Extraction.model_validate(
            {
                "roles": [
                    {"speaker": "A", "role": "doctor", "evidence_ids": ["u1", "bad"]}
                ],
                "facts": [],
                "summary_bn": "",
                "warnings": [],
            }
        ),
        [{"id": "u1", "speaker": "A", "text": "কী সমস্যা?"}],
    )
    assert result["roles"][0]["role"] == "doctor"
    assert result["roles"][0]["evidence_ids"] == ["u1"]
    assert warnings


def test_noise_snr_seed_and_no_clipping():
    from backend.audio import add_noise

    clean = (0.1 * np.sin(np.arange(16000) * 0.07)).astype(np.float32)
    noisy, meta = add_noise(clean, 20)
    again, _ = add_noise(clean, 20)
    assert np.array_equal(noisy, again)
    assert np.max(np.abs(noisy)) <= 1
    measured = 10 * np.log10(np.mean(clean**2) / np.mean((noisy - clean) ** 2))
    assert abs(measured - 20) < 0.01
    assert meta["seed"] == 42


def test_chunk_invocations_and_timestamp_offsets(monkeypatch):
    import sys, types
    from backend.pipeline import stage_stt

    class Model:
        def __init__(self, *args, **kwargs):
            assert kwargs["compute_type"] == "int8"

        def transcribe(self, audio, **kwargs):
            assert kwargs["language"] == "bn"
            assert kwargs["without_timestamps"] is True
            segment = types.SimpleNamespace(
                start=0, end=len(audio) / 16000, text="পরীক্ষা", words=[]
            )
            return iter([segment]), None

    monkeypatch.setitem(
        sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model)
    )
    ledger = []
    segments = stage_stt(
        np.zeros(65 * 16000, dtype=np.float32),
        lambda *args: None,
        ledger,
        "chunks",
        30,
        Path("fake-model"),
    )
    assert len(ledger) == 3
    assert [s["start"] for s in segments] == [0, 30, 60]
    assert segments[-1]["end"] == 65


def test_single_worker_rejects_concurrent_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(server.cfg, "ROOT", tmp_path)
    monkeypatch.setattr(server.cfg, "DATA", tmp_path / "data")
    monkeypatch.setattr(server, "active", None)

    class Worker:
        def submit(self, fn):
            pass

    monkeypatch.setattr(server, "worker", Worker())
    source = tmp_path / "source.wav"
    source.write_bytes(b"fixture")
    options = Options(use_llm=False)
    first = server.launch(source, options, "fixture.wav")
    assert first["status"] == "queued"
    with pytest.raises(server.HTTPException) as error:
        server.launch(source, options, "fixture.wav")
    assert error.value.status_code == 409
