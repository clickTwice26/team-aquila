"""Corpus regression guard for multilingual case_type accuracy.

Runs the generated multilingual fixture (tests/cases.json) through the true app
classification path (rules + optional ML fallback) and asserts the accuracy
floor by language. This guards against keyword/regex regressions, especially
for Bangla and romanized Banglish inputs.

Thresholds are conservative floors (the current build scores ~99% / 100% / 98%);
they catch regressions without being flaky on the few genuinely-ambiguous cases.
"""
from __future__ import annotations

import json
import os
from collections import Counter

import pytest

from queuestorm.domain.investigator import _final_classification
from queuestorm.domain.normalization import build_signals

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FIXTURE = os.path.join(_ROOT, "tests", "cases.json")

OVERALL_FLOOR = 0.95
PER_LANGUAGE_FLOOR = 0.90


def _load():
    if not os.path.exists(_FIXTURE) or os.path.getsize(_FIXTURE) == 0:
        return None
    with open(_FIXTURE, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["cases"] if isinstance(data, dict) else data


def _score():
    cases = _load()
    if not cases:
        pytest.skip("tests/cases.json missing or empty")
    tot, ok = Counter(), Counter()
    for c in cases:
        lang = c.get("language", "en")
        got = _final_classification(build_signals(c["complaint"], lang)).case_type.value
        tot[lang] += 1
        tot["__all__"] += 1
        if got == c["expected_case_type"]:
            ok[lang] += 1
            ok["__all__"] += 1
    return tot, ok


def test_overall_accuracy_floor():
    tot, ok = _score()
    acc = ok["__all__"] / tot["__all__"]
    assert acc >= OVERALL_FLOOR, f"overall case_type accuracy {acc:.3f} < {OVERALL_FLOOR}"


@pytest.mark.parametrize("lang", ["en", "bn", "mixed"])
def test_per_language_floor(lang):
    tot, ok = _score()
    if not tot.get(lang):
        pytest.skip(f"no {lang} cases in fixture")
    acc = ok[lang] / tot[lang]
    assert acc >= PER_LANGUAGE_FLOOR, f"{lang} accuracy {acc:.3f} < {PER_LANGUAGE_FLOOR}"
