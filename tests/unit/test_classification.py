"""Unit tests for rule-based case_type classification & tie-break order."""
from __future__ import annotations

import pytest

from queuestorm.domain.classification import classify_rules
from queuestorm.domain.normalization import build_signals
from queuestorm.schemas.enums import CaseType


@pytest.mark.parametrize("text,expected", [
    ("Someone called asking for my OTP, is this real?", CaseType.phishing_or_social_engineering),
    ("I paid 850 but it deducted twice", CaseType.duplicate_payment),
    ("I sent money to the wrong number by mistake", CaseType.wrong_transfer),
    ("payment showed failed but balance was deducted", CaseType.payment_failed),
    ("cash in through agent but balance not updated", CaseType.agent_cash_in_issue),
    ("my merchant settlement has not arrived", CaseType.merchant_settlement_delay),
    ("I want a refund, I changed my mind", CaseType.refund_request),
    ("something is wrong with my money", CaseType.other),
])
def test_classification(text, expected):
    assert classify_rules(build_signals(text)).case_type == expected


def test_phishing_wins_tiebreak_even_with_amount():
    # Mentions OTP + a refund-like phrase: phishing must win.
    text = "Someone wants my OTP and says they will refund 500 to me"
    assert classify_rules(build_signals(text)).case_type == CaseType.phishing_or_social_engineering


def test_duplicate_beats_generic_refund():
    text = "I was charged twice, please refund the duplicate"
    assert classify_rules(build_signals(text)).case_type == CaseType.duplicate_payment


def test_wrong_transfer_beats_refund_when_reverse_requested():
    text = "I sent it to the wrong number, please reverse it"
    assert classify_rules(build_signals(text)).case_type == CaseType.wrong_transfer


def test_unclassified_is_low_confidence():
    c = classify_rules(build_signals("hello"))
    assert c.case_type == CaseType.other
    assert c.confidence < 0.6
