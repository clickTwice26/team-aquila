"""Transaction matching and evidence verdict — the core of Evidence Reasoning.

Given the complaint signals, the chosen case_type, and the transaction history,
decide relevant_transaction_id (a real id from history, or None) and
evidence_verdict (consistent | inconsistent | insufficient_data).

Discipline: when several transactions plausibly match and nothing disambiguates,
return None + insufficient_data rather than guessing.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas.enums import CaseType, EvidenceVerdict
from .normalization import ComplaintSignals

_EXPECTED_TYPES: dict[CaseType, set[str]] = {
    CaseType.wrong_transfer: {"transfer"},
    CaseType.payment_failed: {"payment", "transfer"},
    CaseType.refund_request: {"payment", "transfer"},
    CaseType.duplicate_payment: {"payment", "transfer"},
    CaseType.merchant_settlement_delay: {"settlement"},
    CaseType.agent_cash_in_issue: {"cash_in"},
}


@dataclass
class Transaction:
    transaction_id: str | None
    timestamp: str | None
    type: str | None
    amount: float | None
    counterparty: str | None
    status: str | None


@dataclass
class MatchResult:
    relevant_transaction_id: str | None
    evidence_verdict: EvidenceVerdict
    reason_codes: list[str]
    ambiguous: bool = False


def _amount_matches(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) < 0.01


def _norm_cp(value: str | None) -> str:
    return (value or "").lower().lstrip("+").lstrip("0")


def _hint_matches_cp(hints: list[str], counterparty: str | None) -> bool:
    cp = _norm_cp(counterparty)
    if not cp:
        return False
    for hint in hints:
        h = _norm_cp(hint)
        if h and (h.endswith(cp[-8:]) or cp.endswith(h[-8:]) or h == cp):
            return True
    return False


def _score(txn: Transaction, signals: ComplaintSignals, case_type: CaseType) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if _amount_matches(signals.primary_amount, txn.amount):
        score += 100
        reasons.append("amount_match")
    if txn.type in _EXPECTED_TYPES.get(case_type, set()):
        score += 12
        reasons.append("type_match")
    if case_type == CaseType.payment_failed and txn.status == "failed":
        score += 15
        reasons.append("status_failed")
    if signals.mentions_not_received and txn.status == "pending":
        score += 12
        reasons.append("status_pending")
    if _hint_matches_cp(signals.counterparty_hints, txn.counterparty):
        score += 50
        reasons.append("counterparty_match")
    return score, reasons


def _duplicate_pair(txns: list[Transaction]) -> Transaction | None:
    """Find a near-identical pair (same amount + counterparty) and return the
    LATER one (the suspected duplicate)."""
    for i in range(len(txns)):
        for j in range(len(txns)):
            if i == j:
                continue
            a, b = txns[i], txns[j]
            if (
                _amount_matches(a.amount, b.amount)
                and _norm_cp(a.counterparty) == _norm_cp(b.counterparty)
                and _norm_cp(a.counterparty) != ""
            ):
                return b if (b.timestamp or "") >= (a.timestamp or "") else a
    return None


def _established_recipient(matched: Transaction, txns: list[Transaction]) -> bool:
    """True if there is >=1 OTHER completed transfer to the same counterparty."""
    cp = _norm_cp(matched.counterparty)
    if not cp:
        return False
    for t in txns:
        if t is matched:
            continue
        if t.type == "transfer" and t.status == "completed" and _norm_cp(t.counterparty) == cp:
            return True
    return False


def match(signals: ComplaintSignals, case_type: CaseType, txns: list[Transaction]) -> MatchResult:
    if not txns:
        return MatchResult(None, EvidenceVerdict.insufficient_data, ["no_transaction_history"])

    # duplicate_payment: pick the suspected duplicate (the later txn).
    if case_type == CaseType.duplicate_payment:
        dup = _duplicate_pair(txns)
        if dup is not None and dup.transaction_id:
            return MatchResult(dup.transaction_id, EvidenceVerdict.consistent,
                               ["duplicate_pair_detected", "selected_later_txn"])
        single = _best_single(signals, case_type, txns)
        if single is not None and single.transaction_id:
            return MatchResult(single.transaction_id, EvidenceVerdict.inconsistent,
                               ["no_duplicate_pair_found"])
        return MatchResult(None, EvidenceVerdict.insufficient_data, ["no_matching_transaction"])

    scored = [(t, *_score(t, signals, case_type)) for t in txns]
    strong = [(t, s, r) for (t, s, r) in scored if s >= 100]

    if not strong:
        return MatchResult(
            None,
            EvidenceVerdict.insufficient_data,
            ["no_amount_match"] if signals.primary_amount is not None
            else ["no_specific_transaction_referenced"],
        )

    if len(strong) == 1:
        txn = strong[0][0]
        verdict, vr = _verdict_for_single(txn, signals, case_type, txns)
        return MatchResult(txn.transaction_id, verdict, strong[0][2] + vr)

    # Multiple amount matches — a counterparty hint can single one out.
    hinted = [(t, s, r) for (t, s, r) in strong if "counterparty_match" in r]
    if len(hinted) == 1:
        txn = hinted[0][0]
        verdict, vr = _verdict_for_single(txn, signals, case_type, txns)
        return MatchResult(txn.transaction_id, verdict, hinted[0][2] + vr)

    distinct_cps = {_norm_cp(t.counterparty) for (t, _, _) in strong}
    if len(distinct_cps) > 1:
        return MatchResult(None, EvidenceVerdict.insufficient_data,
                           ["multiple_plausible_transactions", "needs_clarification"], ambiguous=True)

    latest = max((t for (t, _, _) in strong), key=lambda t: t.timestamp or "")
    verdict, vr = _verdict_for_single(latest, signals, case_type, txns)
    return MatchResult(latest.transaction_id, verdict, ["selected_most_recent_match"] + vr)


def _best_single(signals: ComplaintSignals, case_type: CaseType, txns: list[Transaction]) -> Transaction | None:
    scored = [(t, *_score(t, signals, case_type)) for t in txns]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0] if scored and scored[0][1] >= 100 else None


def _verdict_for_single(
    txn: Transaction, signals: ComplaintSignals, case_type: CaseType, txns: list[Transaction]
) -> tuple[EvidenceVerdict, list[str]]:
    """Default consistent; downgrade only when the data contradicts the story."""
    if case_type == CaseType.wrong_transfer:
        if _established_recipient(txn, txns):
            return EvidenceVerdict.inconsistent, ["established_recipient_pattern"]
        return EvidenceVerdict.consistent, ["transaction_match"]

    if case_type == CaseType.payment_failed:
        if txn.status == "failed":
            return EvidenceVerdict.consistent, ["failed_with_possible_deduction"]
        if txn.status == "completed":
            return EvidenceVerdict.inconsistent, ["claimed_failed_but_completed"]
        return EvidenceVerdict.consistent, ["payment_under_review"]

    if case_type == CaseType.agent_cash_in_issue:
        return EvidenceVerdict.consistent, ["cash_in_pending_or_missing"]

    if case_type == CaseType.merchant_settlement_delay:
        return EvidenceVerdict.consistent, ["settlement_pending"]

    if case_type == CaseType.refund_request:
        return EvidenceVerdict.consistent, ["original_payment_found"]

    return EvidenceVerdict.consistent, ["transaction_match"]
