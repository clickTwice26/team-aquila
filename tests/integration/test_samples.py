"""Functional-equivalence tests against all 10 public sample cases.

Equivalence is judged on the six scored fields (per the problem statement):
relevant_transaction_id, evidence_verdict, case_type, department, severity,
human_review_required. The customer_reply must additionally be safe.
"""
from __future__ import annotations

import json
import os

import pytest

from queuestorm.domain.investigator import analyze
from queuestorm.domain.parsing import parse_ticket
from queuestorm.domain.safety import is_safe

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(_ROOT, "contexts", "SUST_Preli_Sample_Cases.json"), encoding="utf-8") as _fh:
    _CASES = json.load(_fh)["cases"]

SCORED = ["relevant_transaction_id", "evidence_verdict", "case_type", "department",
          "severity", "human_review_required"]


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_scored_fields_match_expected(case):
    expected = case["expected_output"]
    out = analyze(parse_ticket(case["input"])).model_dump()
    mismatches = {k: (out.get(k), expected.get(k)) for k in SCORED if out.get(k) != expected.get(k)}
    assert not mismatches, f"{case['id']} mismatches (got, expected): {mismatches}"


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_customer_reply_is_safe(case):
    out = analyze(parse_ticket(case["input"])).model_dump()
    assert is_safe(out["customer_reply"]), f"{case['id']} unsafe reply: {out['customer_reply']}"
    assert is_safe(out["recommended_next_action"]), f"{case['id']} unsafe action"


def test_bangla_case_replies_in_bangla():
    case = next(c for c in _CASES if c["id"] == "SAMPLE-07")
    out = analyze(parse_ticket(case["input"])).model_dump()
    # Reply should contain Bangla script and the Bangla credential reminder.
    assert any("ঀ" <= ch <= "৿" for ch in out["customer_reply"])
    assert "পিন" in out["customer_reply"]
