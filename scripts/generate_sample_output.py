"""Generate sample_output.json from the public sample cases.

Runs every public sample `input` through the investigator and writes our
responses (alongside the published `expected_output`) to sample_output.json —
a required deliverable and a quick self-check of functional equivalence.

Usage:
    python scripts/generate_sample_output.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from queuestorm.domain.investigator import analyze  # noqa: E402
from queuestorm.domain.parsing import parse_ticket  # noqa: E402

SAMPLES = os.path.join(ROOT, "contexts", "SUST_Preli_Sample_Cases.json")
OUT = os.path.join(ROOT, "sample_output.json")

SCORED = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]


def main() -> int:
    with open(SAMPLES, encoding="utf-8") as fh:
        pack = json.load(fh)

    results = []
    matches = 0
    for case in pack["cases"]:
        inp = case["input"]
        expected = case.get("expected_output", {})
        ours = analyze(parse_ticket(inp)).model_dump()

        scored_ok = all(ours.get(k) == expected.get(k) for k in SCORED)
        sev_ok = ours.get("severity") == expected.get("severity")
        hr_ok = ours.get("human_review_required") == expected.get("human_review_required")
        if scored_ok and sev_ok and hr_ok:
            matches += 1

        results.append({
            "id": case.get("id"),
            "label": case.get("label"),
            "input": inp,
            "our_output": ours,
            "expected_output": expected,
            "scored_fields_match": scored_ok,
            "severity_match": sev_ok,
            "human_review_match": hr_ok,
        })
        status = "OK " if (scored_ok and sev_ok and hr_ok) else "DIFF"
        print(f"[{status}] {case.get('id')}: {ours['case_type']} / "
              f"{ours['evidence_verdict']} / {ours['department']} / "
              f"{ours['severity']} / hr={ours['human_review_required']}")

    payload = {
        "_meta": {
            "service": "queuestorm-investigator",
            "source_cases": "SUST_Preli_Sample_Cases.json "
                            "(referenced in the problem statement as QueueStorm_Preli_Sample_Cases.json)",
            "cases_fully_matching_expected": f"{matches}/{len(results)}",
            "note": "Other valid responses exist; equivalence is judged on the scored fields.",
        },
        "cases": results,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"\nWrote {OUT}  ({matches}/{len(results)} cases match expected on all six scored fields)")
    return 0 if matches == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
