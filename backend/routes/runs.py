from __future__ import annotations
import asyncio
import json
import uuid
from pathlib import Path
from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from .. import settings as cfg
from fastapi import APIRouter
from .. import jobs
from ..jobs import run_dir, read_json
from ..schemas import Options, ExtractionPermission

router = APIRouter()


@router.post("/api/runs/sample", status_code=202)
def run_sample(options: Options):
    audio = list((cfg.ROOT / "conversation").glob("*.m4a"))
    if not audio:
        raise HTTPException(404, "Conversation audio missing")
    return jobs.launch(audio[0], options, audio[0].name)


@router.post("/api/runs/upload", status_code=202)
async def run_upload(options: str = Form(...), audio: UploadFile = File(...)):
    try:
        parsed = Options.model_validate_json(options)
    except ValueError:
        raise HTTPException(422, "Invalid run options or remote permission missing")
    extension = Path(audio.filename or "").suffix.lower()
    if extension not in [
        ".wav",
        ".m4a",
        ".mp4",
        ".aac",
        ".mp3",
        ".ogg",
        ".webm",
        ".flac",
    ]:
        raise HTTPException(415, "Unsupported audio extension")
    target = cfg.DATA / "uploads" / (uuid.uuid4().hex + extension)
    size = 0
    try:
        with target.open("wb") as handle:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > 50 * 1024 * 1024:
                    raise HTTPException(413, "Maximum upload is 50 MB")
                handle.write(chunk)
        if not size:
            raise HTTPException(400, "Empty file")
        return jobs.launch(target, parsed, Path(audio.filename).name)
    except Exception:
        target.unlink(missing_ok=True)
        raise


@router.get("/api/runs")
def runs():
    output = []
    for path in sorted(
        (cfg.DATA / "runs").glob("*/job.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        job = read_json(path)
        if (
            job["status"] not in ["completed", "partial", "failed"]
            and job["id"] != jobs.active
        ):
            job["status"] = "interrupted"
        output.append(job)
    return output


@router.get("/api/runs/{run_id}")
def run_status(run_id: str):
    path = run_dir(run_id)
    job = read_json(path / "job.json")
    if (
        job["status"] not in ["completed", "partial", "failed"]
        and jobs.active != run_id
    ):
        job["status"] = "interrupted"
    result = (
        read_json(path / "result.json") if (path / "result.json").exists() else None
    )
    return {"job": job, "result": result}


@router.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request):
    run_dir(run_id)

    async def generate():
        last = ""
        while not await request.is_disconnected():
            status = run_status(run_id)
            serialized = json.dumps(status["job"], ensure_ascii=False)
            if serialized != last:
                yield "data: " + serialized + "\n\n"
                last = serialized
            else:
                yield ": keepalive\n\n"
            if status["job"]["status"] in [
                "completed",
                "partial",
                "failed",
                "interrupted",
            ]:
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


@router.get("/api/runs/{run_id}/download")
def download(run_id: str):
    directory = run_dir(run_id)
    path = directory / "result.json"
    if not path.exists():
        raise HTTPException(404, "No result yet")
    report = read_json(path)
    report["evaluation_reference"] = (
        read_json(directory / "reference.json")
        if (directory / "reference.json").exists()
        else None
    )
    report["source_audio_embedded"] = False
    return JSONResponse(
        report,
        headers={
            "Content-Disposition": f'attachment; filename="meddesk-run-{run_id}.json"'
        },
    )


@router.get("/api/runs/{run_id}/audio")
def run_audio(run_id: str):
    meta = run_dir(run_id) / "source.json"
    if not meta.exists():
        raise HTTPException(404, "Source mapping unavailable for this older run")
    path = (cfg.ROOT / read_json(meta)["relative_path"]).resolve()
    if not path.is_relative_to(cfg.ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, "Audio not found")
    return FileResponse(path)


@router.post("/api/runs/{run_id}/extract", status_code=202)
def retry_extraction(run_id: str, permission: ExtractionPermission):
    return jobs.retry_extraction(run_id, permission)
