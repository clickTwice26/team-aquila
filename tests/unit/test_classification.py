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


# --- Multilingual: Bangla script + romanized Banglish must classify too. ---
@pytest.mark.parametrize("text,lang,expected", [
    # Bangla script
    ("ভুল নম্বরে টাকা পাঠিয়ে ফেলেছি ফেরত চাই", "bn", CaseType.wrong_transfer),
    ("পেমেন্ট ফেইল হয়েছে কিন্তু টাকা কেটে নিয়েছে", "bn", CaseType.payment_failed),
    ("একই বিল দুইবার কেটেছে", "bn", CaseType.duplicate_payment),
    ("রিফান্ড চাই পণ্য লাগবে না", "bn", CaseType.refund_request),
    ("এজেন্টের কাছে ক্যাশ ইন করেছি কিন্তু ব্যালেন্সে আসেনি", "bn", CaseType.agent_cash_in_issue),
    ("আমার বিক্রির টাকা সেটেল হয়নি", "bn", CaseType.merchant_settlement_delay),
    ("কেউ ফোন দিয়ে আমার ওটিপি চাইছে", "bn", CaseType.phishing_or_social_engineering),
    # Romanized Banglish (the previously-failing bucket)
    ("vul number e taka pathaisi ferot chai", "mixed", CaseType.wrong_transfer),
    ("bhul manush ke taka pathaye disi", "mixed", CaseType.wrong_transfer),
    ("payment fail holo kintu taka kete nilo", "mixed", CaseType.payment_failed),
    ("bill dite gie fail hoise but balance kome gese", "mixed", CaseType.payment_failed),
    ("ek bill dui bar kete nise", "mixed", CaseType.duplicate_payment),
    ("ami refund chai product lagbe na", "mixed", CaseType.refund_request),
    ("agent er kache cash in korsi but balance e ase nai", "mixed", CaseType.agent_cash_in_issue),
    ("amar merchant settlement ase nai", "mixed", CaseType.merchant_settlement_delay),
    ("keu amar otp chasche bole account block hobe", "mixed", CaseType.phishing_or_social_engineering),
])
def test_multilingual_classification(text, lang, expected):
    assert classify_rules(build_signals(text, lang)).case_type == expected


def test_merchant_keyword_does_not_hijack_refund():
    # SAMPLE-04 style: a refund that merely mentions "merchant" must stay refund.
    text = "I paid 500 to a merchant for a product but changed my mind, refund please"
    assert classify_rules(build_signals(text)).case_type == CaseType.refund_request
