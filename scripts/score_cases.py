"""Score the rule classifier against a multilingual case_type fixture.

Reports case_type accuracy overall, by language, and by case_type, and lists
the misses so they can be triaged (app gap vs. ambiguous label).

Usage:
    python scripts/score_cases.py [path/to/cases.json]
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from queuestorm.domain.classification import classify_rules  # noqa: E402
from queuestorm.domain.normalization import build_signals  # noqa: E402

LANGS = ["en", "bn", "mixed"]


def main(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cases = data["cases"] if isinstance(data, dict) else data

    tot = Counter()
    ok = Counter()
    by_type_tot = Counter()
    by_type_ok = Counter()
    misses = []
    for c in cases:
        text, lang, exp = c["complaint"], c.get("language", "en"), c["expected_case_type"]
        got = classify_rules(build_signals(text, lang)).case_type.value
        tot[lang] += 1
        by_type_tot[exp] += 1
        if got == exp:
            ok[lang] += 1
            by_type_ok[exp] += 1
        else:
            misses.append((lang, exp, got, text))

    n = sum(tot.values())
    print(f"=== case_type accuracy on {n} cases ===")
    print(f"OVERALL: {sum(ok.values())}/{n} = {100*sum(ok.values())/n:.1f}%\n")
    print("by language:")
    for lang in LANGS:
        if tot[lang]:
            print(f"  {lang:6s}: {ok[lang]:3d}/{tot[lang]:3d} = {100*ok[lang]/tot[lang]:.1f}%")
    print("\nby case_type:")
    for t in sorted(by_type_tot):
        print(f"  {t:32s}: {by_type_ok[t]:3d}/{by_type_tot[t]:3d} = {100*by_type_ok[t]/by_type_tot[t]:.1f}%")

    if misses:
        print(f"\n=== {len(misses)} misses ===")
        conf = defaultdict(int)
        for lang, exp, got, _ in misses:
            conf[(exp, got)] += 1
        print("confusion (expected -> got : count):")
        for (exp, got), cnt in sorted(conf.items(), key=lambda x: -x[1]):
            print(f"  {exp} -> {got}: {cnt}")
        print("\nexamples:")
        for lang, exp, got, text in misses[:25]:
            print(f"  [{lang}] exp={exp} got={got} | {text[:90]}")
    return 0


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tests", "cases.json")
    sys.exit(main(p))
