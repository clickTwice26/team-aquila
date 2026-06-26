"""Strict response model — response_model enforces the contract on the wire."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import CaseType, Department, EvidenceVerdict, Severity


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    ticket_id: str
    relevant_transaction_id: str | None = None
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)


def assert_valid_enums(payload: dict[str, Any]) -> None:
    """Test-time guard: fail loudly on any enum typo in a serialised response."""
    checks = {
        "evidence_verdict": {e.value for e in EvidenceVerdict},
        "case_type": {e.value for e in CaseType},
        "severity": {e.value for e in Severity},
        "department": {e.value for e in Department},
    }
    for field, allowed in checks.items():
        value = payload.get(field)
        if value not in allowed:
            raise ValueError(f"Invalid enum for {field!r}: {value!r} not in {sorted(allowed)}")
