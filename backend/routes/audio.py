from fastapi import (
    APIRouter,
    HTTPException,
)
from ..jobs import run_dir

router = APIRouter()


@router.get("/api/runs/{run_id}/enhanced-audio")
def enhanced_audio(run_id: str):
    from fastapi.responses import FileResponse

    path = run_dir(run_id) / "enhanced.wav"
    if not path.is_file():
        raise HTTPException(404, "This run has no enhanced audio")
    return FileResponse(path, media_type="audio/wav")
