from __future__ import annotations
import hashlib
from urllib.parse import urlparse
from .. import settings as cfg
from ..stt import model_ready
from fastapi import APIRouter
from .. import jobs

router = APIRouter()


@router.get("/api/health")
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
        "active_run": jobs.active,
        "modes": ["batch", "chunks"],
        "transport_note": "File upload uses HTTP; live PCM uses WebSocket. SSE/polling deliver final-job status.",
    }
