"""Feature boundaries: consent, encryption, unknown matches and live cleanup."""

import numpy as np
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend import app as server, voices, feature_routes, llm


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server.cfg, "DATA", tmp_path)
    (tmp_path / "uploads").mkdir()
    (tmp_path / "runs").mkdir()
    monkeypatch.setattr(server, "active", None)
    monkeypatch.setenv("VOICE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return TestClient(server.app)


def test_profile_route_precedes_static_catchall(client):
    assert client.get("/api/voices").json()["profiles"] == []
    assert client.get("/features.js").status_code == 200
    assert client.get("/live-worklet.js").status_code == 200


@pytest.mark.parametrize("name,consent", [("Test", False), ("bad\x00name", True)])
def test_enrollment_permission_and_name_validation(client, name, consent):
    response = client.post(
        "/api/voices",
        data={"name": name, "role": "doctor", "consent": str(consent).lower()},
        files={"audio": ("sample.wav", b"not audio")},
    )
    assert response.status_code == 422
    assert server.active is None


def test_encrypted_profile_roundtrip_and_deletion(client, monkeypatch):
    monkeypatch.setattr(
        voices, "embedding", lambda audio: np.array([1.0, 0.0], dtype=np.float32)
    )
    monkeypatch.setattr(voices, "sha256", lambda _: "test-model")
    row = voices.enroll("Doctor Example", "doctor", np.zeros(48000))
    payload = (server.cfg.DATA / "voices/templates.enc").read_bytes()
    assert b"Doctor Example" not in payload and b"embedding" not in payload
    profile = client.get("/api/voices").json()["profiles"][0]
    assert profile["id"] == row["id"] and "embedding" not in profile
    assert client.delete("/api/voices/" + row["id"]).json()["deleted"]
    assert client.get("/api/voices").json()["profiles"] == []


def test_ambiguous_and_incompatible_voices_remain_unknown(monkeypatch):
    monkeypatch.setattr(server.cfg, "VOICE_THRESHOLD", 0.7)
    monkeypatch.setattr(server.cfg, "VOICE_MARGIN", 0.1)
    a = {
        "id": "a",
        "name": "A",
        "role": "doctor",
        "model_sha256": "v1",
        "embedding": [1, 0],
    }
    b = dict(a, id="b", name="B", embedding=[0.999, 0.001])
    assert voices.match(np.array([1.0, 0.0]), [a, b], "v1")["status"] == "unknown"
    assert voices.match(np.array([1.0, 0.0]), [a], "v2")["status"] == "unknown"
    assert voices.match(np.array([0.0, 1.0]), [a], "v1")["status"] == "unknown"
    assert voices.match(np.array([1.0, 0.0]), [a], "v1")["profile_id"] == "a"


@pytest.mark.parametrize("headers", [{}, {"origin": "https://untrusted.example"}])
def test_websocket_requires_exact_same_origin(client, headers):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect("/api/live", headers=headers):
            pass
    assert error.value.code == 1008


def test_live_rejects_missing_recording_consent(client):
    with client.websocket_connect(
        "/api/live", headers={"origin": "http://testserver"}
    ) as socket:
        socket.send_json({"type": "start", "sample_rate": 16000, "consent": False})
        assert socket.receive_json()["type"] == "error"
    assert server.active is None


class FakeLive:
    instances = []

    def __init__(self):
        self.frames = self.samples = 0
        self.closed = False
        self.__class__.instances.append(self)

    def feed(self, packet):
        if len(packet) % 2:
            raise ValueError("Invalid PCM")
        self.frames += 1
        self.samples += len(packet) // 2
        return "test draft"

    def finish(self):
        return "test final"

    def summary(self):
        return {"decoder_steps": 2, "audio_seconds": self.samples / 16000}

    def close(self):
        self.closed = True


def config():
    return {
        "type": "start",
        "sample_rate": 16000,
        "consent": True,
        "options": {"max_seconds": 0, "use_llm": False},
    }


def test_live_disconnect_closes_model_deletes_audio_releases_slot(client, monkeypatch):
    monkeypatch.setattr(feature_routes, "LiveRecognizer", FakeLive)
    with client.websocket_connect(
        "/api/live", headers={"origin": "http://testserver"}
    ) as socket:
        socket.send_json(config())
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(b"\x00\x00" * 1600)
        assert socket.receive_json()["ack"] == 1
    assert FakeLive.instances[-1].closed
    assert server.active is None
    assert not list((server.cfg.DATA / "uploads").glob("live-*.wav"))


def test_live_final_handoff_passes_own_reservation(client, monkeypatch):
    monkeypatch.setattr(feature_routes, "LiveRecognizer", FakeLive)

    def launch(source, options, name, context, reservation):
        assert server.active == reservation
        assert source.is_file() and context["draft_transcript"] == "test final"
        server.active = "queued-final"
        return {"id": "queued-final", "status": "queued"}

    monkeypatch.setattr(server, "launch", launch)
    with client.websocket_connect(
        "/api/live", headers={"origin": "http://testserver"}
    ) as socket:
        socket.send_json(config())
        socket.receive_json()
        socket.send_bytes(b"\x00\x00" * 16000)
        socket.receive_json()
        socket.send_json({"type": "stop"})
        assert socket.receive_json()["final_run"]["id"] == "queued-final"
    assert server.active == "queued-final"
    assert FakeLive.instances[-1].closed
    assert len(list((server.cfg.DATA / "uploads").glob("live-*.wav"))) == 1


def test_llm_provider_never_receives_voice_identity_on_retry(monkeypatch):
    import httpx

    monkeypatch.setattr(server.cfg, "LLM_KEY", "test-key")
    monkeypatch.setattr(server.cfg, "LLM_BASE", "https://provider.example/v1")
    monkeypatch.setattr(server.cfg, "LLM_MODEL", "test-model")

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            prompt = json["messages"][1]["content"]
            assert "PRIVATE_ENROLLMENT_NAME" not in prompt
            assert "voice_identity" not in prompt and "embedding" not in prompt
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"roles":[],"facts":[],"summary_bn":"","warnings":[]}'
                            },
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

    monkeypatch.setattr(llm.httpx, "Client", Client)
    llm.extract(
        [
            {
                "id": "u1",
                "speaker": "A",
                "start": 0,
                "end": 1,
                "text": "test speech",
                "voice_identity": {
                    "name": "PRIVATE_ENROLLMENT_NAME",
                    "embedding": [1, 2],
                },
            }
        ],
        [],
    )


def test_synthetic_signal_metrics_use_actual_error_energy():
    from backend.enhancement import synthetic_metrics

    t = np.arange(16000, dtype=np.float32) / 16000
    reference = np.sin(2 * np.pi * 220 * t)
    noisy = reference + np.sqrt(0.1) * np.sin(2 * np.pi * 440 * t)
    metrics = synthetic_metrics(reference, noisy)
    assert metrics["snr_db"] == pytest.approx(10, abs=0.02)
    assert metrics["si_sdr_db"] == pytest.approx(10, abs=0.02)
    assert synthetic_metrics(np.zeros(100), np.zeros(100))["snr_db"] is None


def test_failed_encrypted_store_replace_preserves_previous_profiles(
    client, monkeypatch
):
    voices._write([{"id": "old"}])

    def fail(*args):
        raise PermissionError("simulated locked file")

    monkeypatch.setattr(voices.os, "replace", fail)
    with pytest.raises(PermissionError):
        voices._write([{"id": "new"}])
    assert voices._read() == [{"id": "old"}]
    assert not (server.cfg.DATA / "voices/templates.tmp").exists()


def test_signature_rejects_silence_without_model_load():
    with pytest.raises(RuntimeError, match="silent"):
        voices.embedding(np.zeros(16000 * 5, dtype=np.float32))
