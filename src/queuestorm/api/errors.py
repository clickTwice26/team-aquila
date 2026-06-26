"""Controlled, non-sensitive error responses. Never leak stack traces/secrets."""
from __future__ import annotations

from typing import Any

import orjson
from starlette.responses import Response


def error_response(status: int, message: str, ticket_id: Any = None) -> Response:
    body: dict[str, Any] = {"error": message}
    if isinstance(ticket_id, str) and ticket_id:
        body["ticket_id"] = ticket_id
    return Response(content=orjson.dumps(body), media_type="application/json", status_code=status)
