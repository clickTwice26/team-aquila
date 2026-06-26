"""Single source-of-truth enum tables.

OUTPUT enums are exact strings — any variant is a schema violation. Emitting a
value outside these sets is impossible because the response model is typed with
them. INPUT value sets are validated softly (unknown values are tolerated).
"""
from __future__ import annotations

from enum import StrEnum


class EvidenceVerdict(StrEnum):
    consistent = "consistent"
    inconsistent = "inconsistent"
    insufficient_data = "insufficient_data"


class CaseType(StrEnum):
    wrong_transfer = "wrong_transfer"
    payment_failed = "payment_failed"
    refund_request = "refund_request"
    duplicate_payment = "duplicate_payment"
    merchant_settlement_delay = "merchant_settlement_delay"
    agent_cash_in_issue = "agent_cash_in_issue"
    phishing_or_social_engineering = "phishing_or_social_engineering"
    other = "other"


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Department(StrEnum):
    customer_support = "customer_support"
    dispute_resolution = "dispute_resolution"
    payments_ops = "payments_ops"
    merchant_operations = "merchant_operations"
    agent_operations = "agent_operations"
    fraud_risk = "fraud_risk"


# Input enum value sets (soft validation only).
LANGUAGES = {"en", "bn", "mixed"}
CHANNELS = {"in_app_chat", "call_center", "email", "merchant_portal", "field_agent"}
USER_TYPES = {"customer", "merchant", "agent", "unknown"}
TXN_TYPES = {"transfer", "payment", "cash_in", "cash_out", "settlement", "refund"}
TXN_STATUSES = {"completed", "failed", "pending", "reversed"}
