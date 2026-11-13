import uuid
import unicodedata
from pathlib import Path
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool
from .. import settings as cfg
from ..audio import decode_clip
from .. import voices
from ..jobs import reserve, release

router = APIRouter()


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
        raise HTTPException(422, "Provide a name (1â€“120 characters) and valid role")
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
            raise HTTPException(422, "Upload only 3â€“30 seconds of one speaker")
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
