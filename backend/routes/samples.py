from __future__ import annotations
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .. import settings as cfg
from ..core import docx_script
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/sample")
def sample():
    audio = list((cfg.ROOT / "conversation").glob("*.m4a"))
    document = cfg.ROOT / "conversation" / "script.docx"
    return {
        "audio_available": bool(audio),
        "audio_name": audio[0].name if audio else None,
        "script": docx_script(document) if document.exists() else [],
        "verified": False,
        "note": "Provided reading script is not automatically verified against audio. Never given to the LLM as an answer.",
    }


@router.get("/api/sample/audio")
def sample_audio():
    audio = list((cfg.ROOT / "conversation").glob("*.m4a"))
    if not audio:
        raise HTTPException(404, "Supplied conversation not found")
    return FileResponse(audio[0], media_type="audio/mp4")
