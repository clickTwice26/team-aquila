"""HTTP middleware: per-request timing header + structured access logging."""
from __future__ import annotations

import time

from fastapi import FastAPI, Request

from ..core.logging import get_logger

log = get_logger("queuestorm.api")


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.2f}"
        if request.url.path == "/analyze-ticket":
            log.info("analyze status=%s latency_ms=%.2f", response.status_code, elapsed_ms)
        return response
