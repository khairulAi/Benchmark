from __future__ import annotations
import time
from fastapi import HTTPException
from ..core import atomic_json
from ..evaluation import score
from fastapi import APIRouter
from .. import jobs
from ..jobs import run_dir, read_json
from ..schemas import Reference

router = APIRouter()


@router.put("/api/runs/{run_id}/reference")
def reference(run_id: str, reference: Reference):
    path = run_dir(run_id)
    if jobs.active == run_id:
        raise HTTPException(409, "Wait until this run finishes")
    if not (path / "result.json").exists():
        raise HTTPException(409, "No result to evaluate")
    result = read_json(path / "result.json")
    if result["status"] == "failed":
        raise HTTPException(409, "Failed run cannot be scored")
    ref = reference.model_dump()
    if any(
        s["end"] > result["audio"]["analyzed_seconds"] + 0.01
        for s in ref.get("speaker_segments") or []
    ):
        raise HTTPException(
            422, "Reference timestamps must fall within the analyzed clip"
        )
    ref["saved_at"] = time.time()
    ref["audio_sha256"] = result["audio"]["sha256"]
    ref["clip_options"] = result["options"]
    result["metrics"] = score(result, ref)
    atomic_json(path / "reference.json", ref)
    atomic_json(path / "result.json", result)
    return result["metrics"]


@router.get("/api/runs/{run_id}/reference")
def get_reference(run_id: str):
    path = run_dir(run_id) / "reference.json"
    return (
        read_json(path)
        if path.exists()
        else {
            "transcript": "",
            "verified": False,
            "verification_note": "",
            "speaker_segments": None,
            "facts": None,
        }
    )
