"""Gunicorn configuration for horizontal scaling under load.

The service is stateless and CPU-light (rules path ~1-5ms), so throughput
scales with worker PROCESSES. We run UvicornWorker (ASGI) and preload the app
so the optional ML model loads once in the master and is shared copy-on-write
across forked workers.

Run:
    gunicorn -c deploy/gunicorn_conf.py queuestorm.main:app
"""
from __future__ import annotations

import multiprocessing
import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


_cpu = multiprocessing.cpu_count()

# CPU-bound work -> processes ~= cores (override with WEB_CONCURRENCY).
workers = _int("WEB_CONCURRENCY", max(2, _cpu))
worker_class = "uvicorn.workers.UvicornWorker"

bind = f"{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8000')}"
worker_connections = _int("WORKER_CONNECTIONS", 1000)

# Preload -> shared memory for the model, faster boot.
preload_app = True

# Recycle workers to bound memory; jitter avoids a thundering herd.
max_requests = _int("MAX_REQUESTS", 20000)
max_requests_jitter = _int("MAX_REQUESTS_JITTER", 2000)

keepalive = _int("KEEPALIVE", 15)
timeout = _int("WORKER_TIMEOUT", 30)
graceful_timeout = 30

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
