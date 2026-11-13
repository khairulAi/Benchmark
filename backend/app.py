from __future__ import annotations
import asyncio
import json
import re
import threading
import time
import uuid
import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import settings as cfg
from .core import StrictModel, atomic_json, docx_script
from .evaluation import score
from .pipeline import run_pipeline
from .stt import model_ready
from .llm import extract

app = FastAPI(title="MedDesk Bengali Benchmark", version="2.0.0")
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
)
worker = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
active = None


@app.middleware("http")
async def protect(request, call_next):
    if request.method == "POST" and request.url.path in (
        "/api/runs/upload",
        "/api/voices",
    ):
        size = request.headers.get("content-length")
        if size is None:
            return JSONResponse({"detail": "Content-Length required for uploads"}, 411)
        if not size.isdigit():
            return JSONResponse({"detail": "Invalid Content-Length"}, 400)
        if int(size) > 52 * 1024 * 1024:
            return JSONResponse({"detail": "Multipart request exceeds 52 MB"}, 413)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return __import__(
                "starlette.responses", fromlist=["JSONResponse"]
            ).JSONResponse({"detail": "Cross-origin mutation blocked"}, 403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


class Options(StrictModel):
    denoise: bool = False
    identify_voices: bool = False
    stt_profile: str = Field(
        default=cfg.DEFAULT_STT_PROFILE,
        pattern="^(bangla_asr|vivasoft|zipformer|indicconformer)$",
    )
    offset_seconds: float = Field(default=0, ge=0, le=7200)
    max_seconds: int = Field(default=120, ge=0, le=1200)
    num_speakers: int = Field(default=2, ge=1, le=6)
    strategy: str = Field(default="batch", pattern="^(batch|chunks)$")
    chunk_seconds: int = Field(default=30, ge=10, le=120)
    noise_snr_db: float | None = Field(default=None, ge=-5, le=40)
    use_llm: bool = True
    remote_permission: bool = False

    @model_validator(mode="after")
    def permission(self):
        if self.use_llm and not self.remote_permission:
            raise ValueError(
                "Confirm permission to send transcript to the configured LLM provider"
            )
        return self


class TimedReference(StrictModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker: str = Field(min_length=1, max_length=100)
    role: str = Field(default="unknown", pattern="^(doctor|patient|unknown)$")

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("end must exceed start")
        return self


class ExpectedFact(StrictModel):
    category: str
    value: str = Field(min_length=1)
    polarity: str = Field(pattern="^(present|absent|uncertain)$")


class Reference(StrictModel):
    transcript: str = Field(max_length=200000)
    verified: bool = False
    verification_note: str = Field(default="", max_length=2000)
    speaker_segments: list[TimedReference] | None = None
    facts: list[ExpectedFact] | None = None

    @model_validator(mode="after")
    def valid(self):
        if self.verified and not self.transcript.strip():
            raise ValueError("Verified transcript cannot be empty")
        return self


class ExtractionPermission(StrictModel):
    remote_permission: bool


def run_dir(run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(404, "Run not found")
    path = cfg.DATA / "runs" / run_id
    if not path.exists():
        raise HTTPException(404, "Run not found")
    return path


def read_json(path):
    return json.loads(path.read_text("utf-8"))


@app.get("/api/health")
def health():
    return {
        "version": "2.0.0",
        "workspace_id": hashlib.sha256(str(cfg.ROOT).encode()).hexdigest()[:12],
        "llm_configured": bool(cfg.LLM_KEY and cfg.LLM_BASE and cfg.LLM_MODEL),
        "llm_provider": urlparse(cfg.LLM_BASE).hostname,
        "llm_model": cfg.LLM_MODEL,
        "stt_model": cfg.STT_PROFILES[cfg.DEFAULT_STT_PROFILE][0],
        "default_stt_profile": cfg.DEFAULT_STT_PROFILE,
        "denoiser_ready": cfg.DENOISER.is_file(),
        "streaming_ready": __import__(
            "backend.streaming", fromlist=["streaming_ready"]
        ).streaming_ready(),
        "speaker_models_ready": cfg.SEGMENTATION.exists() and cfg.EMBEDDING.exists(),
        "stt_profiles": {
            key: {"model": value[0], "ready": model_ready(key, value[1])}
            for key, value in cfg.STT_PROFILES.items()
        },
        "models_ready": model_ready(
            cfg.DEFAULT_STT_PROFILE, cfg.STT_PROFILES[cfg.DEFAULT_STT_PROFILE][1]
        )
        and all(p.exists() for p in [cfg.SEGMENTATION, cfg.EMBEDDING]),
        "cpu_threads": cfg.THREADS,
        "active_run": active,
        "modes": ["batch", "chunks"],
        "transport_note": "File upload uses HTTP; live PCM uses WebSocket. SSE/polling deliver final-job status.",
    }


@app.get("/api/sample")
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


@app.get("/api/sample/audio")
def sample_audio():
    audio = list((cfg.ROOT / "conversation").glob("*.m4a"))
    if not audio:
        raise HTTPException(404, "Supplied conversation not found")
    return FileResponse(audio[0], media_type="audio/mp4")


def launch(source, options, source_name, context=None, reservation=None):
    global active
    with lock:
        if active and active != reservation:
            raise HTTPException(
                409,
                "Another run is active. This CPU workspace processes one run at a time.",
            )
        run_id = uuid.uuid4().hex
        path = cfg.DATA / "runs" / run_id
        path.mkdir(parents=True)
        atomic_json(
            path / "source.json",
            {"relative_path": str(source.resolve().relative_to(cfg.ROOT.resolve()))},
        )
        atomic_json(
            path / "job.json",
            {
                "id": run_id,
                "status": "queued",
                "source_name": source_name,
                "created_at": time.time(),
                "options": options.model_dump(),
            },
        )
        active = run_id

    def update(stage, extra):
        job = read_json(path / "job.json")
        job.update(extra)
        job["status"] = stage
        job["updated_at"] = time.time()
        atomic_json(path / "job.json", job)

    def execute():
        global active
        try:
            run_options = options.model_dump()
            if context is not None:
                run_options["streaming_context"] = context
            run_pipeline(run_id, source, run_options, update)
        except Exception:
            update(
                "failed",
                {"error": "Worker failed unexpectedly; outputs may be incomplete."},
            )
        finally:
            with lock:
                active = None

    worker.submit(execute)
    return {"id": run_id, "status": "queued"}


@app.post("/api/runs/sample", status_code=202)
def run_sample(options: Options):
    audio = list((cfg.ROOT / "conversation").glob("*.m4a"))
    if not audio:
        raise HTTPException(404, "Conversation audio missing")
    return launch(audio[0], options, audio[0].name)


@app.post("/api/runs/upload", status_code=202)
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
        return launch(target, parsed, Path(audio.filename).name)
    except Exception:
        target.unlink(missing_ok=True)
        raise


@app.get("/api/runs")
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
            and job["id"] != active
        ):
            job["status"] = "interrupted"
        output.append(job)
    return output


@app.get("/api/runs/{run_id}")
def run_status(run_id: str):
    path = run_dir(run_id)
    job = read_json(path / "job.json")
    if job["status"] not in ["completed", "partial", "failed"] and active != run_id:
        job["status"] = "interrupted"
    result = (
        read_json(path / "result.json") if (path / "result.json").exists() else None
    )
    return {"job": job, "result": result}


@app.get("/api/runs/{run_id}/events")
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


@app.put("/api/runs/{run_id}/reference")
def reference(run_id: str, reference: Reference):
    path = run_dir(run_id)
    if active == run_id:
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


@app.get("/api/runs/{run_id}/download")
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


@app.get("/api/runs/{run_id}/audio")
def run_audio(run_id: str):
    meta = run_dir(run_id) / "source.json"
    if not meta.exists():
        raise HTTPException(404, "Source mapping unavailable for this older run")
    path = (cfg.ROOT / read_json(meta)["relative_path"]).resolve()
    if not path.is_relative_to(cfg.ROOT.resolve()) or not path.is_file():
        raise HTTPException(404, "Audio not found")
    return FileResponse(path)


@app.get("/api/runs/{run_id}/reference")
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


@app.post("/api/runs/{run_id}/extract", status_code=202)
def retry_extraction(run_id: str, permission: ExtractionPermission):
    global active
    if not permission.remote_permission:
        raise HTTPException(422, "Transcript-sharing permission required")
    parent = run_dir(run_id)
    if not (parent / "result.json").exists():
        raise HTTPException(409, "Parent run has no result")
    base = read_json(parent / "result.json")
    if base.get("status") not in ["completed", "partial"] or not base.get("transcript"):
        raise HTTPException(409, "Parent transcript is not ready")
    with lock:
        if active:
            raise HTTPException(409, "A run is already active")
        child = uuid.uuid4().hex
        path = cfg.DATA / "runs" / child
        path.mkdir()
        active = child
    options = copy.deepcopy(base["options"])
    options.update(use_llm=True, remote_permission=True)
    job = {
        "id": child,
        "status": "extracting",
        "source_name": "Reused transcript " + run_id[:8],
        "created_at": time.time(),
        "options": options,
        "parent_run": run_id,
    }
    atomic_json(path / "job.json", job)
    if (parent / "source.json").exists():
        atomic_json(path / "source.json", read_json(parent / "source.json"))

    def execute():
        global active
        tick = time.perf_counter()
        result = copy.deepcopy(base)
        result.update(
            id=child,
            status="running",
            stage="extracting",
            created_at=time.time(),
            options=options,
            ledger=[],
            metrics=None,
            extraction=None,
            parent_run=run_id,
            execution_kind="extraction_only",
            timings={},
            warnings=[
                "STT and diarization reused from parent run; latency is extraction-only and must not be compared as a full pipeline run."
            ],
            peak_process_rss_mb=None,
        )
        result.pop("llm_error", None)
        result.pop("error", None)
        for utterance in result["transcript"]:
            utterance["role"] = "unknown"
        result["models"]["llm_configured_id"] = cfg.LLM_MODEL
        try:
            atomic_json(path / "result.json", result)
            result["extraction"], warnings = extract(
                result["transcript"], result["ledger"]
            )
            result["warnings"].extend(
                warnings + result["extraction"].get("warnings", [])
            )
            role_map = {r["speaker"]: r["role"] for r in result["extraction"]["roles"]}
            for utterance in result["transcript"]:
                utterance["role"] = role_map.get(utterance["speaker"], "unknown")
            result["status"] = "completed"
        except Exception as error:
            result["status"] = "partial"
            result["llm_error"] = (
                str(error) if isinstance(error, RuntimeError) else "Extraction failed"
            )
        finally:
            result["stage"] = result["status"]
            result["timings"]["llm_seconds"] = round(time.perf_counter() - tick, 3)
            result["timings"]["total_seconds"] = result["timings"]["llm_seconds"]
            result["timings"]["real_time_factor"] = None
            result["calls"] = {
                "stt_local_invocations": 0,
                "diarization_local_invocations": 0,
                "llm_http_attempts": len(result["ledger"]),
                "note": "Extraction-only run; no local model was invoked.",
            }
            costs = [e.get("cost_usd") for e in result["ledger"]]
            result["cost_usd"] = (
                sum(costs) if costs and all(c is not None for c in costs) else None
            )
            atomic_json(path / "result.json", result)
            job["status"] = result["status"]
            atomic_json(path / "job.json", job)
            with lock:
                active = None

    worker.submit(execute)
    return {"id": child, "status": "extracting", "parent_run": run_id}


from .feature_routes import router as feature_router

app.include_router(feature_router)

# Explicit static allowlist: never serve .env, model files, uploads, .git or arbitrary paths.
STATIC = {
    "": "index.html",
    "index.html": "index.html",
    "style.css": "style.css",
    "app.js": "app.js",
    "benchmark.html": "benchmark.html",
    "benchmark.js": "benchmark.js",
    "features.js": "features.js",
    "live-worklet.js": "live-worklet.js",
    "benchmark.css": "benchmark.css",
    "test.html": "test.html",
    "test.js": "test.js",
}


@app.get("/{asset:path}")
def static(asset: str):
    name = STATIC.get(asset)
    if name:
        return FileResponse(cfg.ROOT / name)
    if asset in ["audio/khairul.aac", "audio/mahamudul.mp4", "audio/shawon.ogg"]:
        path = cfg.ROOT / asset
        if path.exists():
            return FileResponse(path)
    raise HTTPException(404, "Not found")
