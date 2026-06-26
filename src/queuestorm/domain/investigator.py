"""The investigation pipeline orchestrator (application service).

parse → classify case_type → match transaction → judge verdict → route
department → set severity → set human_review → draft text → enforce safety.

The deterministic rule engine decides all six scored fields. The optional ML
fallback only assists case_type when the rules are not confident, and never
overrides a confident phishing/safety classification. The safety filter runs
last and is the final, independent guarantee.
"""
from __future__ import annotations

from functools import lru_cache

from ..core.config import settings
from ..ml import classifier as ml_classifier
from ..schemas.enums import CaseType
from ..schemas.response import AnalyzeResponse
from . import safety
from .classification import Classification, classify_rules
from .matching import Transaction, match
from .normalization import build_signals
from .parsing import ParsedTicket
from .routing import assess_severity, needs_human_review, route_department
from .templates import build_agent_summary, build_customer_reply, build_next_action

# If rule confidence >= this, trust the rules outright (skip ML entirely).
_ML_ELIGIBLE_FLOOR = 0.6


def _final_classification(signals) -> Classification:
    rules = classify_rules(signals)

    if rules.confidence >= _ML_ELIGIBLE_FLOOR or rules.case_type == CaseType.phishing_or_social_engineering:
        return rules
    if not settings.USE_ML_FALLBACK:
        return rules

    prediction = ml_classifier.predict(signals.raw)
    if prediction is None:
        return rules
    label, proba = prediction
    if proba < settings.ML_CONFIDENCE_THRESHOLD:
        return rules
    # Never let ML escalate to fraud off weak signal without rule corroboration.
    if label == CaseType.phishing_or_social_engineering and rules.case_type != label:
        return rules
    return Classification(label, proba, rules.reason_codes + [f"ml:{label.value}"], "rules+ml")


def _investigate(ticket: ParsedTicket) -> AnalyzeResponse:
    signals = build_signals(ticket.complaint, ticket.language)

    classification = _final_classification(signals)
    case_type = classification.case_type

    match_result = match(signals, case_type, ticket.transactions)
    verdict = match_result.evidence_verdict
    rel_id = match_result.relevant_transaction_id

    department = route_department(case_type, ticket.user_type, verdict)
    severity = assess_severity(case_type, verdict, signals.primary_amount)
    human_review = needs_human_review(case_type, verdict, rel_id, signals.primary_amount)

    matched_txn: Transaction | None = next(
        (t for t in ticket.transactions if t.transaction_id == rel_id), None
    )

    agent_summary = build_agent_summary(case_type, verdict, matched_txn, signals.primary_amount, ticket.user_type)
    next_action = build_next_action(case_type, verdict, rel_id, department)
    customer_reply = build_customer_reply(case_type, signals.language, signals.raw, rel_id)

    customer_reply, next_action, safety_flags = safety.enforce(
        customer_reply, next_action, signals.language, signals.raw, case_type
    )

    reason_codes = list(dict.fromkeys(classification.reason_codes + match_result.reason_codes))
    if safety_flags:
        reason_codes.append("safety_filtered")

    confidence = round(min(classification.confidence, 0.97), 2)
    if verdict.value == "insufficient_data":
        confidence = min(confidence, 0.65)

    return AnalyzeResponse(
        ticket_id=ticket.ticket_id,
        relevant_transaction_id=rel_id,
        evidence_verdict=verdict,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=agent_summary,
        recommended_next_action=next_action,
        customer_reply=customer_reply,
        human_review_required=human_review,
        confidence=confidence,
        reason_codes=reason_codes,
    )


def _content_signature(ticket: ParsedTicket) -> tuple:
    """Hashable signature of ticket CONTENT, excluding ticket_id, so retries of
    the same case hit the cache while the echoed ticket_id stays per-request."""
    txns = tuple(
        (t.transaction_id, t.timestamp, t.type, t.amount, t.counterparty, t.status)
        for t in ticket.transactions
    )
    return (ticket.complaint, ticket.language, ticket.channel, ticket.user_type, txns)


@lru_cache(maxsize=settings.CACHE_SIZE)
def _cached_core(signature: tuple) -> dict:
    """Investigate from a content signature; returns the response sans ticket_id."""
    complaint, language, channel, user_type, txns = signature
    ticket = ParsedTicket(
        ticket_id="",
        complaint=complaint,
        language=language,
        channel=channel,
        user_type=user_type,
        transactions=[Transaction(*t) for t in txns],
    )
    data = _investigate(ticket).model_dump()
    data.pop("ticket_id", None)
    return data


def analyze(ticket: ParsedTicket) -> AnalyzeResponse:
    """Investigate a ticket. Heavy work is cached on content; the echoed
    ticket_id always reflects THIS request."""
    core = dict(_cached_core(_content_signature(ticket)))
    core["ticket_id"] = ticket.ticket_id
    return AnalyzeResponse(**core)
