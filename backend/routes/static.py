from __future__ import annotations
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .. import settings as cfg
from fastapi import APIRouter

router = APIRouter()

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


@router.get("/{asset:path}")
def static(asset: str):
    name = STATIC.get(asset)
    if name:
        return FileResponse(cfg.ROOT / name)
    if asset in ["audio/khairul.aac", "audio/mahamudul.mp4", "audio/shawon.ogg"]:
        path = cfg.ROOT / asset
        if path.exists():
            return FileResponse(path)
    raise HTTPException(404, "Not found")
