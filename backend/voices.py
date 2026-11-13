"""Local speaker enrollment and conservative matching with encrypted templates.

Embeddings and metadata are encrypted with Fernet. On Windows the local key
is itself protected by current-user DPAPI; another OS requires an explicit
VOICE_ENCRYPTION_KEY. Raw enrollment recordings are not retained by this module.
"""

from __future__ import annotations
import ctypes
import gc
import json
import os
import threading
import time
import uuid

import numpy as np
from cryptography.fernet import Fernet, InvalidToken
from . import settings as cfg
from .core import sha256

_STORE_LOCK = threading.RLock()


def _dpapi(data: bytes, decrypt=False) -> bytes:
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    destination = Blob()
    dll = ctypes.windll.crypt32
    # CRYPTPROTECT_UI_FORBIDDEN: no dialogs or machine-wide key protection.
    if decrypt:
        ok = dll.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)
        )
    else:
        ok = dll.CryptProtectData(
            ctypes.byref(source),
            "MedDesk voice templates",
            None,
            None,
            None,
            1,
            ctypes.byref(destination),
        )
    if not ok:
        raise RuntimeError("Windows could not protect/unprotect the voice-store key")
    try:
        return ctypes.string_at(destination.data, destination.size)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(destination.data, ctypes.c_void_p))


def _cipher_unlocked():
    explicit = os.getenv("VOICE_ENCRYPTION_KEY", "").strip()
    if explicit:
        try:
            return Fernet(explicit.encode("ascii"))
        except (ValueError, UnicodeError):
            raise RuntimeError("Invalid VOICE_ENCRYPTION_KEY") from None
    if os.name != "nt":
        raise RuntimeError("Configure VOICE_ENCRYPTION_KEY on non-Windows hosts")
    path = cfg.DATA / "keys" / "voice-key.dpapi"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        payload = _dpapi(Fernet.generate_key())
        try:
            with path.open("xb") as handle:
                handle.write(payload)
        except FileExistsError:
            pass
    return Fernet(_dpapi(path.read_bytes(), decrypt=True))


def _cipher():
    with _STORE_LOCK:
        return _cipher_unlocked()


def _read():
    path = cfg.DATA / "voices" / "templates.enc"
    if not path.exists():
        return []
    try:
        return json.loads(_cipher().decrypt(path.read_bytes()))
    except (InvalidToken, ValueError):
        raise RuntimeError(
            "Voice store cannot be decrypted; check the key and Windows account"
        ) from None


def _write(records):
    path = cfg.DATA / "voices" / "templates.enc"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _cipher().encrypt(json.dumps(records, ensure_ascii=False).encode("utf-8"))
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def public_profiles():
    with _STORE_LOCK:
        return [
            {key: row[key] for key in ("id", "name", "role", "created_at")}
            for row in _read()
        ]


def unit_vector(values):
    vector = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if vector.ndim != 1 or not np.isfinite(vector).all() or norm < 1e-6:
        raise RuntimeError("Invalid speaker embedding")
    return vector / norm


def create_extractor():
    import sherpa_onnx as s

    config = s.SpeakerEmbeddingExtractorConfig(
        model=str(cfg.EMBEDDING), num_threads=min(2, cfg.THREADS), provider="cpu"
    )
    if not config.validate():
        raise RuntimeError("Speaker embedding weights missing")
    return s.SpeakerEmbeddingExtractor(config)


def embedding(audio, extractor=None):
    audio = np.ascontiguousarray(audio, dtype=np.float32)
    if not 3 * 16000 <= len(audio) <= 30 * 16000:
        raise RuntimeError("Use 3–30 seconds of one speaker's speech")
    if not np.isfinite(audio).all() or float(np.sqrt(np.mean(audio**2))) < 0.003:
        raise RuntimeError("Enrollment speech is silent or too quiet")
    from faster_whisper.vad import get_speech_timestamps, VadOptions

    regions = get_speech_timestamps(
        audio,
        VadOptions(
            min_speech_duration_ms=250, min_silence_duration_ms=250, speech_pad_ms=80
        ),
    )
    if not regions:
        raise RuntimeError("No usable speech detected for a voice signature")
    audio = np.concatenate(
        [audio[region["start"] : region["end"]] for region in regions]
    )
    if len(audio) < 3 * 16000:
        raise RuntimeError("At least three seconds of detected speech is required")
    owned = extractor is None
    if owned:
        extractor = create_extractor()
    try:
        stream = extractor.create_stream()
        stream.accept_waveform(16000, audio)
        stream.input_finished()
        if not extractor.is_ready(stream):
            raise RuntimeError("Not enough usable speaker audio")
        return unit_vector(extractor.compute(stream))
    finally:
        if owned:
            del extractor
            gc.collect()


def enroll(name, role, audio):
    vector = embedding(audio)
    row = {
        "id": uuid.uuid4().hex,
        "name": name,
        "role": role,
        "created_at": time.time(),
        "embedding": vector.tolist(),
        "model_sha256": sha256(cfg.EMBEDDING),
    }
    with _STORE_LOCK:
        records = _read()
        if len(records) >= 100:
            raise RuntimeError("Voice profile limit is 100; delete unused profiles")
        records.append(row)
        _write(records)
    return {key: row[key] for key in ("id", "name", "role", "created_at")}


def delete_profile(profile_id):
    with _STORE_LOCK:
        records = _read()
        remaining = [row for row in records if row["id"] != profile_id]
        if len(remaining) == len(records):
            return False
        _write(remaining)
        return True


def match(vector, records, model_hash):
    candidates = []
    for row in records:
        if row.get("model_sha256") != model_hash:
            continue
        template = unit_vector(row["embedding"])
        if template.shape == vector.shape:
            candidates.append((float(np.dot(template, vector)), row))
    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates:
        return {"status": "unknown", "reason": "no compatible enrolled profiles"}
    score, row = candidates[0]
    margin = score - candidates[1][0] if len(candidates) > 1 else None
    accepted = score >= cfg.VOICE_THRESHOLD and (
        margin is None or margin >= cfg.VOICE_MARGIN
    )
    output = {
        "status": "matched" if accepted else "unknown",
        "cosine_similarity": round(score, 4),
        "margin": round(margin, 4) if margin is not None else None,
        "threshold": cfg.VOICE_THRESHOLD,
        "required_margin": cfg.VOICE_MARGIN,
        "note": "Similarity is not probability or verified identity accuracy; thresholds need target-data calibration.",
    }
    if accepted:
        output.update(profile_id=row["id"], name=row["name"], enrolled_role=row["role"])
    return output


def identify(audio, turns, ledger):
    with _STORE_LOCK:
        records = _read()
    if not records:
        return {}, ["No enrolled profiles; voice identities remain unknown."]
    entry = {
        "stage": "voice_identification",
        "call_kind": "local_embedding_match",
        "status": "requested",
    }
    ledger.append(entry)
    tick = time.perf_counter()
    extractor = None
    output = {}
    try:
        extractor = create_extractor()
        model_hash = sha256(cfg.EMBEDDING)
        for speaker in sorted({turn["speaker"] for turn in turns}):
            pieces = []
            count = 0
            for turn in turns:
                if turn["speaker"] != speaker:
                    continue
                # Avoid enrollment/matching on overlapping voices.
                if any(
                    other["speaker"] != speaker
                    and min(turn["end"], other["end"])
                    - max(turn["start"], other["start"])
                    > 0.1
                    for other in turns
                ):
                    continue
                left, right = int(turn["start"] * 16000), int(turn["end"] * 16000)
                piece = audio[left : min(right, left + 15 * 16000 - count)]
                pieces.append(piece)
                count += len(piece)
                if count >= 15 * 16000:
                    break
            if count < 3 * 16000:
                output[speaker] = {
                    "status": "unknown",
                    "reason": "insufficient non-overlapping speech",
                }
                continue
            try:
                output[speaker] = match(
                    embedding(np.concatenate(pieces), extractor), records, model_hash
                )
            except RuntimeError as error:
                output[speaker] = {"status": "unknown", "reason": str(error)}
        entry.update(status="completed", speaker_count=len(output))
        return output, [
            "Voice matches are predictions against enrolled profiles; no speaker-identification accuracy is claimed without human labels."
        ]
    except Exception:
        entry["status"] = "failed"
        raise
    finally:
        entry["latency_seconds"] = round(time.perf_counter() - tick, 3)
        del extractor
        gc.collect()
