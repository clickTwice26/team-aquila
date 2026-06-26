"""POST /analyze-ticket — tolerant parsing, correct status codes, never crashes.

  400 -> malformed JSON / missing required ticket_id|complaint
  422 -> schema-valid but semantically invalid (empty complaint)
  500 -> internal error (non-sensitive body), ticket_id echoed when parseable
  200 -> structured verdict validated by response_model
"""
from __future__ import annotations

import orjson
from fastapi import APIRouter, Request

from ...core.config import settings
from ...core.logging import get_logger
from ...domain.investigator import analyze
from ...domain.parsing import parse_ticket
from ...schemas.response import AnalyzeResponse
from ..errors import error_response

log = get_logger("queuestorm.api")

router = APIRouter()


@router.post("/analyze-ticket", response_model=AnalyzeResponse)
async def analyze_ticket(request: Request):
    raw = await request.body()
    if len(raw) > settings.MAX_BODY_BYTES:
        return error_response(400, "request body too large")

    try:
        body = orjson.loads(raw) if raw else None
    except orjson.JSONDecodeError:
        return error_response(400, "malformed JSON")
    if not isinstance(body, dict):
        return error_response(400, "request body must be a JSON object")

    ticket_id = body.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id.strip():
        return error_response(400, "missing or invalid required field: ticket_id")
    if "complaint" not in body or body.get("complaint") is None:
        return error_response(400, "missing required field: complaint", ticket_id)
    complaint = body.get("complaint")
    if not isinstance(complaint, str):
        return error_response(400, "field 'complaint' must be a string", ticket_id)
    if not complaint.strip():
        return error_response(422, "field 'complaint' must not be empty", ticket_id)

    try:
        return analyze(parse_ticket(body))
    except Exception:  # pragma: no cover - last-resort safety net
        log.exception("internal error while analyzing ticket %s", ticket_id)
        return error_response(500, "internal error", ticket_id)
