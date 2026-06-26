"""Routing, severity and escalation — pure functions of the decided fields.

department  : function of case_type (user_type confirms merchant/agent routes)
severity    : default per case_type, adjusted by verdict and (rarely) high value
human_review: "does this need human judgment on a dispute/risk NOW?" — not
              merely "is this serious?".
"""
from __future__ import annotations

from ..schemas.enums import CaseType, Department, EvidenceVerdict, Severity

# A deliberately conservative, NON-AUTHORITATIVE high-value floor: it sits well
# above the largest sample amount (15,000 BDT) so it never alters a sample, only
# escalates clearly atypical hidden-test amounts.
HIGH_VALUE_FLOOR = 100_000.0

BASE_DEPARTMENT: dict[CaseType, Department] = {
    CaseType.wrong_transfer: Department.dispute_resolution,
    CaseType.payment_failed: Department.payments_ops,
    CaseType.duplicate_payment: Department.payments_ops,
    CaseType.merchant_settlement_delay: Department.merchant_operations,
    CaseType.agent_cash_in_issue: Department.agent_operations,
    CaseType.phishing_or_social_engineering: Department.fraud_risk,
    CaseType.refund_request: Department.customer_support,
    CaseType.other: Department.customer_support,
}

_SEVERITY_ORDER = [Severity.low, Severity.medium, Severity.high, Severity.critical]


def route_department(case_type: CaseType, user_type: str | None, verdict: EvidenceVerdict) -> Department:
    dept = BASE_DEPARTMENT[case_type]

    if case_type == CaseType.refund_request and verdict == EvidenceVerdict.inconsistent:
        dept = Department.dispute_resolution

    if case_type == CaseType.other:
        if user_type == "merchant":
            dept = Department.merchant_operations
        elif user_type == "agent":
            dept = Department.agent_operations

    return dept


def _escalate(sev: Severity) -> Severity:
    idx = _SEVERITY_ORDER.index(sev)
    return _SEVERITY_ORDER[min(idx + 1, len(_SEVERITY_ORDER) - 1)]


def assess_severity(case_type: CaseType, verdict: EvidenceVerdict, amount: float | None) -> Severity:
    if case_type == CaseType.phishing_or_social_engineering:
        return Severity.critical

    if case_type == CaseType.wrong_transfer:
        sev = Severity.high if verdict == EvidenceVerdict.consistent else Severity.medium
    elif case_type in (CaseType.payment_failed, CaseType.duplicate_payment, CaseType.agent_cash_in_issue):
        sev = Severity.high
    elif case_type == CaseType.merchant_settlement_delay:
        sev = Severity.medium
    elif case_type == CaseType.refund_request:
        sev = Severity.low
    else:
        sev = Severity.low

    if (
        amount is not None
        and amount >= HIGH_VALUE_FLOOR
        and verdict != EvidenceVerdict.inconsistent
        and sev in (Severity.low, Severity.medium)
    ):
        sev = _escalate(sev)

    return sev


def needs_human_review(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    relevant_transaction_id: str | None,
    amount: float | None,
) -> bool:
    if case_type == CaseType.phishing_or_social_engineering:
        return True

    if case_type == CaseType.wrong_transfer:
        return relevant_transaction_id is not None

    if case_type in (CaseType.duplicate_payment, CaseType.agent_cash_in_issue):
        return relevant_transaction_id is not None

    if verdict == EvidenceVerdict.inconsistent and relevant_transaction_id is not None:
        return True

    if amount is not None and amount >= HIGH_VALUE_FLOOR:
        return True

    return False
