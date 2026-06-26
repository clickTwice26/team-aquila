"""Optional tiny local fallback classifier for case_type.

A hedge, never the source of truth. A small scikit-learn TF-IDF + Logistic
Regression pipeline (~tens of KB), trained offline by
scripts/train_classifier.py. Runs on CPU, in-process, no network, sub-ms.

Consulted ONLY when the rule classifier is not confident, and it can never
override a confident phishing/safety classification (the caller guards that).
If scikit-learn or the artifact is unavailable, this module silently disables
itself and the service keeps working on rules alone.
"""
from __future__ import annotations

import os
import threading

from ..core.config import settings
from ..core.logging import get_logger
from ..schemas.enums import CaseType

log = get_logger("queuestorm.ml")

_lock = threading.Lock()
_loaded = False
_model = None


def _try_load() -> None:
    global _loaded, _model
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        _loaded = True
        if not settings.USE_ML_FALLBACK:
            log.info("ML fallback disabled by configuration.")
            return
        path = settings.ML_MODEL_PATH
        if not os.path.exists(path):
            log.info("ML fallback model not found at %s — running rules-only.", path)
            return
        try:
            import joblib

            _model = joblib.load(path)
            log.info("ML fallback classifier loaded from %s", path)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Could not load ML fallback (%s) — running rules-only.", exc)
            _model = None


def available() -> bool:
    _try_load()
    return _model is not None


def predict(text: str) -> tuple[CaseType, float] | None:
    """Return (case_type, probability) or None if the model is unavailable."""
    _try_load()
    if _model is None or not text:
        return None
    try:
        proba = _model.predict_proba([text])[0]
        classes = _model.classes_
        best_idx = int(proba.argmax())
        label = str(classes[best_idx])
        confidence = float(proba[best_idx])
        try:
            return CaseType(label), confidence
        except ValueError:
            return None
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("ML prediction failed (%s) — ignoring.", exc)
        return None
