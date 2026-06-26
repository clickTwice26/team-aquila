"""Liveness/readiness endpoints. Static and dependency-free so /health is
green well within the 60-second readiness window, even on a cold start.
"""
from __future__ import annotations

from fastapi import APIRouter

from ...core.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    # Exactly this body. No DB, no model load, no network.
    return {"status": "ok"}


@router.get("/")
async def root() -> dict:
    return {"service": settings.SERVICE_NAME, "version": settings.VERSION, "status": "ok"}
