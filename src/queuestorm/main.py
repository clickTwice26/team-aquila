"""ASGI application factory and entrypoint.

Run (dev):    uvicorn queuestorm.main:app --host 0.0.0.0 --port 8000
Run (scale):  gunicorn -c deploy/gunicorn_conf.py queuestorm.main:app
"""
from __future__ import annotations

from fastapi import FastAPI

from .api.middleware import install_middleware
from .api.routes import analyze, health
from .core.config import settings
from .core.logging import get_logger
from .ml import classifier as ml_classifier

log = get_logger("queuestorm.api")


def create_app() -> FastAPI:
    app = FastAPI(
        title="QueueStorm Investigator",
        description="Evidence-grounded fintech support copilot API (rules-first hybrid).",
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url=None,
    )

    install_middleware(app)
    app.include_router(health.router, tags=["health"])
    app.include_router(analyze.router, tags=["analyze"])

    @app.on_event("startup")
    async def _startup() -> None:
        # Warm the optional ML fallback; /health is already up so this never
        # blocks readiness in practice (tiny artifact, sub-second load).
        try:
            ready = ml_classifier.available()
        except Exception:  # pragma: no cover
            ready = False
        log.info("%s v%s ready (ml_fallback=%s)", settings.SERVICE_NAME, settings.VERSION, ready)

    return app


app = create_app()
