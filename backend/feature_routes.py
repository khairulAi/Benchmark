"""Local voice profiles and live PCM transport endpoints."""

import asyncio
import json
import time
import uuid
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.concurrency import run_in_threadpool

from . import settings as cfg
from .audio import decode_clip
from .streaming import LiveRecognizer
from . import voices

router = APIRouter()


def reserve(identifier):
    from . import app as server

    with server.lock:
        if server.active:
            raise RuntimeError("Another inference job is active; try after it finishes")
        server.active = identifier


def release(identifier):
    from . import app as server

    with server.lock:
        if server.active == identifier:
            server.active = None


@router.get("/api/voices")
def profiles():
    try:
        return {
            "profiles": voices.public_profiles(),
            "threshold": cfg.VOICE_THRESHOLD,
            "margin": cfg.VOICE_MARGIN,
            "calibrated": False,
            "storage": "Fernet encrypted; Windows key protected with user-scoped DPAPI",
        }
    except RuntimeError as error:
        raise HTTPException(503, str(error))


@router.post("/api/voices", status_code=201)
async def enroll_voice(
    name: str = Form(...),
    role: str = Form(...),
    consent: bool = Form(False),
    audio: UploadFile = File(...),
):
    if not consent:
        raise HTTPException(
            422, "Explicit permission is required for biometric voice enrollment"
        )
    if (
        not name.strip()
        or any(unicodedata.category(char) == "Cc" for char in name)
        or len(name.strip()) > 120
        or role not in ("doctor", "patient", "unknown")
    ):
        raise HTTPException(422, "Provide a name (1–120 characters) and valid role")
    if Path(audio.filename or "").suffix.lower() not in (
        ".wav",
        ".m4a",
        ".mp3",
        ".ogg",
        ".webm",
        ".flac",
        ".mp4",
        ".aac",
    ):
        raise HTTPException(415, "Unsupported audio format")
    session = "enrollment-" + uuid.uuid4().hex
    try:
        reserve(session)
    except RuntimeError as error:
        raise HTTPException(409, str(error))
    target = cfg.DATA / "uploads" / (session + Path(audio.filename).suffix.lower())
    try:
        total = 0
        with target.open("wb") as handle:
            while chunk := await audio.read(1024 * 1024):
                total += len(chunk)
                if total > 10 * 1024 * 1024:
                    raise HTTPException(413, "Enrollment audio limit is 10 MB")
                handle.write(chunk)
        samples, duration = await run_in_threadpool(decode_clip, target, 0, 30)
        if duration and duration > 30.1:
            raise HTTPException(422, "Upload only 3–30 seconds of one speaker")
        return await run_in_threadpool(voices.enroll, name.strip(), role, samples)
    except RuntimeError as error:
        raise HTTPException(422, str(error))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Cannot read enrollment audio") from None
    finally:
        try:
            target.unlink(missing_ok=True)
        finally:
            release(session)


@router.delete("/api/voices/{profile_id}")
def delete_voice(profile_id: str):
    if not voices.delete_profile(profile_id):
        raise HTTPException(404, "Voice profile not found")
    return {"deleted": True, "id": profile_id}


@router.get("/api/runs/{run_id}/enhanced-audio")
def enhanced_audio(run_id: str):
    from .app import run_dir
    from fastapi.responses import FileResponse

    path = run_dir(run_id) / "enhanced.wav"
    if not path.is_file():
        raise HTTPException(404, "This run has no enhanced audio")
    return FileResponse(path, media_type="audio/wav")


@router.websocket("/api/live")
async def live(websocket: WebSocket):
    from . import app as server

    # WebSocket handshakes bypass HTTP origin middleware. Validate exact host
    # and origin here; reject browser origins from other websites.
    host = websocket.headers.get("host", "")
    origin = websocket.headers.get("origin")
    if host.split(":")[0] not in ("localhost", "127.0.0.1", "testserver") or (
        origin is None or origin not in ("http://" + host, "https://" + host)
    ):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    identifier = uuid.uuid4().hex
    target = cfg.DATA / "uploads" / ("live-" + identifier + ".wav")
    model = None
    handle = None
    completed = False
    owned = False
    deadline = time.monotonic() + 1250
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=15)
        if len(raw) > 8192:
            raise ValueError("Oversized session configuration")
        config = json.loads(raw)
        if (
            config.get("type") != "start"
            or config.get("sample_rate") != 16000
            or config.get("consent") is not True
        ):
            raise ValueError(
                "Start requires explicit recording permission and 16000 Hz PCM"
            )
        options = server.Options.model_validate(config.get("options", {}))
        if options.offset_seconds != 0 or options.max_seconds not in (0, 1200):
            raise ValueError("Live final analysis must use the complete captured clip")
        reserve("live-" + identifier)
        owned = True
        model = await run_in_threadpool(LiveRecognizer)
        handle = sf.SoundFile(
            target, mode="w", samplerate=16000, channels=1, subtype="PCM_16"
        )
        await websocket.send_json(
            {
                "type": "ready",
                "session_id": identifier,
                "sample_rate": 16000,
                "draft_model": "Vosk Bengali streaming INT8",
                "final_model": options.stt_profile,
            }
        )
        while time.monotonic() < deadline:
            packet = await asyncio.wait_for(websocket.receive(), timeout=30)
            if packet["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()
            pcm = packet.get("bytes")
            if pcm is not None:
                text = await run_in_threadpool(model.feed, pcm)
                handle.write(np.frombuffer(pcm, dtype="<i2"))
                await websocket.send_json(
                    {
                        "type": "partial",
                        "text": text,
                        "ack": model.frames,
                        "audio_seconds": model.samples / 16000,
                    }
                )
            else:
                message = packet.get("text", "")
                if len(message) > 1024 or json.loads(message).get("type") != "stop":
                    raise ValueError("Expected PCM bytes or stop message")
                text = await run_in_threadpool(model.finish)
                summary = model.summary()
                summary["draft_transcript"] = text
                handle.close()
                handle = None
                await run_in_threadpool(model.close)
                model = None
                queued = server.launch(
                    target,
                    options,
                    "Live microphone conversation",
                    context=summary,
                    reservation="live-" + identifier,
                )
                owned = False
                completed = True
                await websocket.send_json(
                    {
                        "type": "final",
                        "text": text,
                        "streaming": summary,
                        "final_run": queued,
                    }
                )
                await websocket.close(code=1000)
                return
        raise ValueError("Session wall-clock limit reached")
    except WebSocketDisconnect:
        pass
    except Exception as error:
        # Do not expose provider data, credentials or stack traces.
        detail = (
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Live session failed or timed out"
        )
        try:
            await websocket.send_json({"type": "error", "detail": detail[:500]})
            await websocket.close(code=1008)
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        try:
            if handle is not None:
                handle.close()
            if model is not None:
                await run_in_threadpool(model.close)
        finally:
            if owned:
                release("live-" + identifier)
            if not completed:
                target.unlink(missing_ok=True)
