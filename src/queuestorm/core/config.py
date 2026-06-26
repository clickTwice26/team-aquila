"""Application settings — sourced exclusively from environment variables.

No secrets are hard-coded. Every setting has a safe default so the service runs
out of the box on the winning rules-only path with zero configuration.
"""
from __future__ import annotations

import os
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL = _PACKAGE_ROOT / "ml" / "artifacts" / "case_type_clf.joblib"


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class Settings:
    """Process-wide settings, read once at import time."""

    # --- Service identity ---------------------------------------------------
    SERVICE_NAME: str = "queuestorm-investigator"
    VERSION: str = "1.0.0"

    # --- Networking ---------------------------------------------------------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _as_int(os.getenv("PORT"), 8000)

    # --- Optional local ML fallback classifier ------------------------------
    # The rule engine is always the source of truth. When it is NOT confident
    # about case_type, we may consult a tiny offline scikit-learn classifier
    # (CPU, in-process, no network, sub-millisecond).
    USE_ML_FALLBACK: bool = _as_bool(os.getenv("USE_ML_FALLBACK"), True)
    ML_MODEL_PATH: str = os.getenv("ML_MODEL_PATH", str(_DEFAULT_MODEL))
    ML_CONFIDENCE_THRESHOLD: float = _as_float(os.getenv("ML_CONFIDENCE_THRESHOLD"), 0.45)

    # --- Performance --------------------------------------------------------
    CACHE_SIZE: int = _as_int(os.getenv("CACHE_SIZE"), 2048)
    MAX_BODY_BYTES: int = _as_int(os.getenv("MAX_BODY_BYTES"), 256 * 1024)

    # --- Observability ------------------------------------------------------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG: bool = _as_bool(os.getenv("DEBUG"), False)


settings = Settings()
