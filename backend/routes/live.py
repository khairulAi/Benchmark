import asyncio
import json
import time
import uuid
import numpy as np
import soundfile as sf
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)
from starlette.concurrency import run_in_threadpool
from .. import settings as cfg
from ..streaming import LiveRecognizer
from ..jobs import reserve, release
from .. import jobs as server
from ..schemas import Options

router = APIRouter()


@router.websocket("/api/live")
async def live(websocket: WebSocket):

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
        options = Options.model_validate(config.get("options", {}))
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
