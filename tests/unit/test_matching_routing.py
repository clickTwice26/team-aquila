"""Unit tests for transaction matching, verdict, routing, severity, escalation."""
from __future__ import annotations

from queuestorm.domain.matching import Transaction, match
from queuestorm.domain.normalization import build_signals
from queuestorm.domain.routing import (
    assess_severity,
    needs_human_review,
    route_department,
)
from queuestorm.schemas.enums import CaseType, Department, EvidenceVerdict, Severity


def _txn(tid, amount, type_="transfer", status="completed", cp="+8801711111111", ts="2026-04-14T10:00:00Z"):
    return Transaction(tid, ts, type_, amount, cp, status)


def test_duplicate_selects_later_txn():
    txns = [
        _txn("TXN-1", 850, "payment", "completed", "BILLER-X", "2026-04-14T08:15:30Z"),
        _txn("TXN-2", 850, "payment", "completed", "BILLER-X", "2026-04-14T08:15:42Z"),
    ]
    res = match(build_signals("paid 850 but deducted twice"), CaseType.duplicate_payment, txns)
    assert res.relevant_transaction_id == "TXN-2"
    assert res.evidence_verdict == EvidenceVerdict.consistent


def test_ambiguous_multiple_recipients_returns_null():
    txns = [
        _txn("TXN-A", 1000, cp="+8801712001122"),
        _txn("TXN-B", 1000, cp="+8801812334455"),
        _txn("TXN-C", 1000, status="failed", cp="+8801712001122"),
    ]
    res = match(build_signals("I sent 1000 to my brother but he didn't get it"),
                CaseType.wrong_transfer, txns)
    assert res.relevant_transaction_id is None
    assert res.evidence_verdict == EvidenceVerdict.insufficient_data


def test_established_recipient_is_inconsistent():
    txns = [
        _txn("TXN-NEW", 2000, cp="+8801812345678", ts="2026-04-14T11:30:00Z"),
        _txn("TXN-OLD1", 2500, cp="+8801812345678", ts="2026-04-10T09:15:00Z"),
        _txn("TXN-OLD2", 1500, cp="+8801812345678", ts="2026-04-05T17:45:00Z"),
    ]
    res = match(build_signals("I sent 2000 to the wrong person, reverse it"),
                CaseType.wrong_transfer, txns)
    assert res.relevant_transaction_id == "TXN-NEW"
    assert res.evidence_verdict == EvidenceVerdict.inconsistent


def test_empty_history_is_insufficient():
    res = match(build_signals("someone asked for my otp"), CaseType.phishing_or_social_engineering, [])
    assert res.relevant_transaction_id is None
    assert res.evidence_verdict == EvidenceVerdict.insufficient_data


def test_department_routing():
    assert route_department(CaseType.wrong_transfer, "customer", EvidenceVerdict.consistent) == Department.dispute_resolution
    assert route_department(CaseType.payment_failed, "customer", EvidenceVerdict.consistent) == Department.payments_ops
    assert route_department(CaseType.phishing_or_social_engineering, None, EvidenceVerdict.insufficient_data) == Department.fraud_risk
    assert route_department(CaseType.other, "merchant", EvidenceVerdict.insufficient_data) == Department.merchant_operations


def test_severity_rules():
    assert assess_severity(CaseType.phishing_or_social_engineering, EvidenceVerdict.insufficient_data, None) == Severity.critical
    assert assess_severity(CaseType.wrong_transfer, EvidenceVerdict.consistent, 5000) == Severity.high
    assert assess_severity(CaseType.wrong_transfer, EvidenceVerdict.inconsistent, 2000) == Severity.medium
    assert assess_severity(CaseType.refund_request, EvidenceVerdict.consistent, 500) == Severity.low
    assert assess_severity(CaseType.merchant_settlement_delay, EvidenceVerdict.consistent, 15000) == Severity.medium


def test_high_value_floor_does_not_alter_samples():
    # 15,000 (largest sample) must NOT be escalated.
    assert assess_severity(CaseType.merchant_settlement_delay, EvidenceVerdict.consistent, 15000) == Severity.medium
    # A clearly atypical amount does escalate.
    assert assess_severity(CaseType.refund_request, EvidenceVerdict.consistent, 250000) == Severity.medium


def test_human_review_rules():
    assert needs_human_review(CaseType.wrong_transfer, EvidenceVerdict.consistent, "TXN-1", 5000) is True
    assert needs_human_review(CaseType.wrong_transfer, EvidenceVerdict.insufficient_data, None, 1000) is False
    assert needs_human_review(CaseType.payment_failed, EvidenceVerdict.consistent, "TXN-1", 1200) is False
    assert needs_human_review(CaseType.refund_request, EvidenceVerdict.consistent, "TXN-1", 500) is False
    assert needs_human_review(CaseType.phishing_or_social_engineering, EvidenceVerdict.insufficient_data, None, None) is True
    assert needs_human_review(CaseType.merchant_settlement_delay, EvidenceVerdict.consistent, "TXN-1", 15000) is False
