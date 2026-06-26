"""Unit tests for complaint normalization & signal extraction."""
from __future__ import annotations

from queuestorm.domain.normalization import (
    build_signals,
    detect_language,
    extract_amounts,
)


def test_amount_ignores_phone_and_time():
    amts = extract_amounts("I sent 5000 taka to 01712345678 around 2pm today")
    assert 5000 in amts
    assert 1712345678 not in amts  # phone not read as amount
    assert 2 not in amts           # "2pm" not read as amount


def test_amount_handles_commas():
    assert 15000 in extract_amounts("my sales of 15,000 taka were not settled")


def test_amount_handles_bangla_digits():
    assert 2000 in extract_amounts("আমি ২০০০ টাকা ক্যাশ ইন করেছি")


def test_language_detection():
    assert detect_language("hello there") == "en"
    assert detect_language("আমার টাকা") == "bn"
    assert detect_language("amar money ফেরত chai") == "mixed"
    assert detect_language("anything", declared="bn") == "bn"


def test_declared_language_overrides_detection():
    assert build_signals("plain english", "bn").language == "bn"


def test_duplicate_and_failed_cues():
    s = build_signals("I was charged twice and one failed")
    assert s.mentions_twice
    assert s.mentions_failed


def test_counterparty_hint_extraction():
    s = build_signals("I cashed in via AGENT-318 but balance not updated")
    assert any("AGENT-318" in h for h in s.counterparty_hints)
