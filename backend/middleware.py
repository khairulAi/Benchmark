"""HTTP upload, origin and response-header protections."""

from fastapi.responses import JSONResponse


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
