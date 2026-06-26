"""Request models — used for OpenAPI docs. Runtime parsing is tolerant
(see queuestorm.domain.parsing) so malformed input never crashes the service.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TransactionEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    timestamp: str | None = None
    type: str | None = None
    amount: float | None = None
    counterparty: str | None = None
    status: str | None = None


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticket_id: str
    complaint: str
    language: str | None = None
    channel: str | None = None
    user_type: str | None = None
    campaign_context: str | None = None
    transaction_history: list[TransactionEntry] | None = None
    metadata: dict | None = None
