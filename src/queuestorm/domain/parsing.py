"""Tolerant request parsing.

Strict on what we EMIT, tolerant of what we RECEIVE. Bad optional fields are
coerced or ignored rather than rejected, so malformed input never crashes the
service. Required-field presence (ticket_id, complaint) is enforced at the API
layer, which maps absence to HTTP 400.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .matching import Transaction


@dataclass
class ParsedTicket:
    ticket_id: str
    complaint: str
    language: str | None = None
    channel: str | None = None
    user_type: str | None = None
    campaign_context: str | None = None
    transactions: list[Transaction] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def _coerce_amount(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def to_transactions(history: Any) -> list[Transaction]:
    """Build a list of Transaction from arbitrary input; skip junk entries."""
    if not isinstance(history, list):
        return []
    txns: list[Transaction] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        txns.append(
            Transaction(
                transaction_id=_coerce_str(entry.get("transaction_id")),
                timestamp=_coerce_str(entry.get("timestamp")),
                type=_coerce_str(entry.get("type")),
                amount=_coerce_amount(entry.get("amount")),
                counterparty=_coerce_str(entry.get("counterparty")),
                status=_coerce_str(entry.get("status")),
            )
        )
    return txns


def parse_ticket(body: dict) -> ParsedTicket:
    """Assumes ticket_id/complaint presence already validated by the caller."""
    meta = body.get("metadata")
    return ParsedTicket(
        ticket_id=str(body.get("ticket_id")),
        complaint=str(body.get("complaint")),
        language=_coerce_str(body.get("language")),
        channel=_coerce_str(body.get("channel")),
        user_type=_coerce_str(body.get("user_type")),
        campaign_context=_coerce_str(body.get("campaign_context")),
        transactions=to_transactions(body.get("transaction_history")),
        metadata=meta if isinstance(meta, dict) else {},
    )
