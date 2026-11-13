"""Shared CPU job lifecycle, reservations and extraction retries."""

from __future__ import annotations
from .schemas import ExtractionPermission
import json
import re
import threading
import time
import uuid
import copy
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from . import settings as cfg
from .core import atomic_json
from .pipeline import run_pipeline
from .llm import extract

worker = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
active = None


def run_dir(run_id):
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise HTTPException(404, "Run not found")
    path = cfg.DATA / "runs" / run_id
    if not path.exists():
        raise HTTPException(404, "Run not found")
    return path


def read_json(path):
    return json.loads(path.read_text("utf-8"))


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


def reserve(identifier):
    global active

    with lock:
        if active:
            raise RuntimeError("Another inference job is active; try after it finishes")
        active = identifier


def release(identifier):
    global active

    with lock:
        if active == identifier:
            active = None
