"""Application composition. Route handlers and processing live in dedicated modules."""

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .middleware import protect
from .routes import health, samples, runs, evaluation, voices, live, audio, static

app = FastAPI(title="MedDesk Bengali Benchmark", version="2.0.0")
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
)
app.middleware("http")(protect)
for module in (health, samples, runs, evaluation, voices, live, audio):
    app.include_router(module.router)
# Catch-all must follow all API routes.
app.include_router(static.router)
