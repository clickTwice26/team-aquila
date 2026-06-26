"""Complaint normalization and signal extraction.

Turns free-form English / Bangla / Banglish complaint text into structured
signals the rule engine reasons over: amounts, language, counterparty hints,
status cues. Pure functions, no I/O — fast and unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Bangla digit -> ASCII digit translation table.
_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_BANGLA_RE = re.compile(r"[ঀ-৿]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Phone numbers / long digit runs (BD formats) — must NOT be read as amounts.
_PHONE_RE = re.compile(r"(?:\+?880\d{8,11}|\b01\d{8,9}\b|\b\d{11,}\b)")
# Time expressions like "2pm", "11 am", "2:47".
_TIME_RE = re.compile(r"\b\d{1,2}\s*(?:am|pm)\b|\b\d{1,2}:\d{2}\b", re.IGNORECASE)
# Transaction-id-like tokens (TXN-9101).
_TXNID_RE = re.compile(r"\b[A-Z]{2,}-?\d+\b", re.IGNORECASE)
# Currency-adjacent number, e.g. "5000 taka", "৳1200", "tk 500", "1200 টাকা".
_CURRENCY_NEAR_RE = re.compile(
    r"(?:৳|tk\.?|bdt)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:taka|tk\.?|৳|bdt|টাকা)",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b([\d,]+(?:\.\d+)?)\b")

_HINT_PHONE_RE = re.compile(r"(?:\+?880\d{8,11}|\b01\d{8,9}\b)")
_HINT_ID_RE = re.compile(r"\b(?:AGENT|MERCHANT|BILLER)[-\s]?[A-Z0-9\-]+\b", re.IGNORECASE)


def detect_language(text: str, declared: str | None = None) -> str:
    """Return 'bn', 'en', or 'mixed'. Trust a valid declared language first."""
    if declared in {"en", "bn", "mixed"}:
        return declared
    has_bangla = bool(_BANGLA_RE.search(text or ""))
    has_latin = bool(_LATIN_RE.search(text or ""))
    if has_bangla and has_latin:
        return "mixed"
    if has_bangla:
        return "bn"
    return "en"


def _to_number(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def extract_amounts(text: str) -> list[float]:
    """Extract plausible BDT amounts, ignoring phone numbers, times and IDs."""
    if not text:
        return []
    work = text.translate(_BANGLA_DIGITS)

    amounts: list[float] = []
    # 1) Strongest: numbers adjacent to a currency marker.
    for m in _CURRENCY_NEAR_RE.finditer(work):
        token = m.group(1) or m.group(2)
        value = _to_number(token) if token else None
        if value is not None and value > 0:
            amounts.append(value)

    # 2) Fallback: bare numbers after masking phones/times/txn-ids.
    masked = _TXNID_RE.sub(" ", work)
    masked = _PHONE_RE.sub(" ", masked)
    masked = _TIME_RE.sub(" ", masked)
    for m in _NUMBER_RE.finditer(masked):
        value = _to_number(m.group(1))
        if value is not None and 1 <= value <= 100_000_000:
            amounts.append(value)

    seen: set[float] = set()
    ordered: list[float] = []
    for value in amounts:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def extract_counterparty_hints(text: str) -> list[str]:
    """Phone numbers / merchant / agent / biller IDs mentioned in the text."""
    if not text:
        return []
    work = text.translate(_BANGLA_DIGITS)
    hints = [m.group(0) for m in _HINT_PHONE_RE.finditer(work)]
    hints += [m.group(0).upper() for m in _HINT_ID_RE.finditer(work)]
    return hints


@dataclass
class ComplaintSignals:
    raw: str
    lower: str
    language: str
    amounts: list[float] = field(default_factory=list)
    counterparty_hints: list[str] = field(default_factory=list)
    mentions_twice: bool = False
    mentions_failed: bool = False
    mentions_not_received: bool = False
    mentions_reverse: bool = False

    @property
    def primary_amount(self) -> float | None:
        return self.amounts[0] if self.amounts else None


def build_signals(complaint: str, declared_language: str | None = None) -> ComplaintSignals:
    text = complaint or ""
    lower = text.lower().translate(_BANGLA_DIGITS)
    return ComplaintSignals(
        raw=text,
        lower=lower,
        language=detect_language(text, declared_language),
        amounts=extract_amounts(text),
        counterparty_hints=extract_counterparty_hints(text),
        mentions_twice=bool(
            re.search(r"\btwice\b|\btwo times\b|\bdouble\b|\bagain\b", lower)
            or "দুইবার" in text or "ডবল" in text
        ),
        mentions_failed=bool(
            re.search(r"\bfail(ed|ure)?\b|\bunsuccessful\b|\bdeclined\b", lower)
            or "ফেইল" in text or "ব্যর্থ" in text or "হয়নি" in text
        ),
        mentions_not_received=bool(
            re.search(r"\bnot (yet )?(received|reflect|credit|come|show|settl)", lower)
            or re.search(r"\bdidn'?t (get|receive)\b|\bhaven'?t (got|received)\b", lower)
            or "আসেনি" in text or "পাইনি" in text or "দেখছি না" in text or "আসে নাই" in text
        ),
        mentions_reverse=bool(
            re.search(r"\breverse\b|\brefund\b|\bget my money back\b|\breturn\b", lower)
            or "ফেরত" in text or "রিফান্ড" in text
        ),
    )
