"""Rule-based case_type classification.

Classifies from the COMPLAINT text only (evidence_verdict is a separate axis).
Returns a confidence score; when the rules are not confident, the caller may
consult the optional local ML fallback. Phishing/safety always wins the
tie-break so a credential-harvesting message can never be mislabelled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas.enums import CaseType
from .normalization import ComplaintSignals

_PATTERNS: dict[CaseType, dict] = {
    CaseType.phishing_or_social_engineering: {
        "regex": re.compile(
            r"\botp\b|\bpin\b|\bpassword\b|\bpass code\b|\bpasscode\b|"
            r"share (your |my )?(code|otp|pin)|account will be (blocked|closed|suspended)|"
            r"\bscam\b|\bphishing\b|\bfraud(ster| caller| call)?\b|claiming to be|"
            r"pretend(ing)? to be|suspicious (call|sms|message|link)|click (this|the) link|"
            r"verify your account|someone called",
            re.IGNORECASE,
        ),
        "bangla": ["ওটিপি", "পিন", "পাসওয়ার্ড", "ব্লক হবে", "প্রতারক", "প্রতারণা",
                    "থেকে বলছি", "লিংক", "সন্দেহজনক", "ফোন দিয়ে"],
    },
    CaseType.duplicate_payment: {
        "regex": re.compile(
            r"\btwice\b|\btwo times\b|\bdouble\b|\bduplicate\b|deducted twice|"
            r"charged (again|twice)|paid once|two times|second time",
            re.IGNORECASE,
        ),
        "bangla": ["দুইবার", "ডবল", "দুই বার", "একবার দিছি", "একবার দিয়েছি"],
    },
    CaseType.wrong_transfer: {
        "regex": re.compile(
            r"wrong (number|person|recipient|account)|sent to (the |a )?wrong|"
            r"typed (it |the number )?wrong|incorrect (number|recipient)|"
            r"by mistake|mistakenly sent|wrong.*transfer",
            re.IGNORECASE,
        ),
        "bangla": ["ভুল নম্বরে", "ভুল লোকে", "ভুল মানুষ", "ভুল করে পাঠ", "ভুল নাম্বার"],
    },
    CaseType.payment_failed: {
        "regex": re.compile(
            r"failed but|showed failed|transaction failed|payment failed|"
            r"recharge failed|bill.*failed|failed.*deduct|deduct.*failed|"
            r"unsuccessful but|declined but",
            re.IGNORECASE,
        ),
        "bangla": ["ফেইল হয়েছে কিন্তু", "ব্যর্থ", "হয়নি কিন্তু টাকা", "ফেইল কিন্তু"],
    },
    CaseType.agent_cash_in_issue: {
        "regex": re.compile(
            r"cash[- ]?in|cash[- ]?out|deposited? (through|via|with) (an )?agent|"
            r"\bagent\b.*(balance|money|cash)|agent.*(sent|deposit)|"
            r"balance.*not.*(reflect|come|add)|did(n'?t| not) (get|reflect).*balance",
            re.IGNORECASE,
        ),
        "bangla": ["ক্যাশ ইন", "ক্যাশইন", "এজেন্ট", "ব্যালেন্সে আসেনি", "ব্যালেন্সে টাকা আসেনি"],
    },
    CaseType.merchant_settlement_delay: {
        "regex": re.compile(
            r"settlement|settle(d|ment)? (not|delay)|not settled|payout|"
            r"my sales|merchant.*(payment|settle)|sales.*(not|delay)",
            re.IGNORECASE,
        ),
        "bangla": ["সেটেলমেন্ট", "মার্চেন্ট", "বিক্রির টাকা", "পেআউট", "সেটেল হয়নি"],
    },
    CaseType.refund_request: {
        "regex": re.compile(
            r"\brefund\b|want my money back|changed my mind|don'?t want (it|the product)|"
            r"\breturn\b|cancel(led)? (the )?(order|payment)|money back",
            re.IGNORECASE,
        ),
        "bangla": ["রিফান্ড", "টাকা ফেরত চাই", "মন বদল", "পণ্য চাই না", "ফেরত দিন"],
    },
}

# Tie-break order (index 0 = highest priority — safety first).
PRIORITY: list[CaseType] = [
    CaseType.phishing_or_social_engineering,
    CaseType.duplicate_payment,
    CaseType.wrong_transfer,
    CaseType.payment_failed,
    CaseType.agent_cash_in_issue,
    CaseType.merchant_settlement_delay,
    CaseType.refund_request,
    CaseType.other,
]


@dataclass
class Classification:
    case_type: CaseType
    confidence: float
    reason_codes: list[str]
    source: str  # "rules" | "rules+ml"


# A money-send verb (EN + Bangla) — used to detect "sent X but not received",
# which is a transfer dispute even without an explicit "wrong" keyword.
_SEND_RE = re.compile(r"\bsent\b|\bsend\b|\btransfer(?:red|ring)?\b|পাঠ", re.IGNORECASE)


def _hits(signals: ComplaintSignals, spec: dict) -> bool:
    if spec["regex"].search(signals.lower):
        return True
    return any(token in signals.raw for token in spec["bangla"])


def _is_transfer_not_received(signals: ComplaintSignals) -> bool:
    return bool(_SEND_RE.search(signals.lower)) and signals.mentions_not_received


def classify_rules(signals: ComplaintSignals) -> Classification:
    """Pure rule classification. Confidence reflects keyword strength."""
    matched: list[CaseType] = [
        ct for ct in PRIORITY if ct in _PATTERNS and _hits(signals, _PATTERNS[ct])
    ]

    if not matched:
        # "I sent money to X but it wasn't received" is a transfer dispute even
        # without an explicit 'wrong' keyword (e.g. SAMPLE-08). Only inferred
        # when no stronger case (agent/merchant/duplicate/...) matched.
        if _is_transfer_not_received(signals):
            return Classification(CaseType.wrong_transfer, 0.72, ["transfer_not_received"], "rules")
        return Classification(CaseType.other, 0.30, ["unclassified_by_rules"], "rules")

    winner = next(ct for ct in PRIORITY if ct in matched)
    base = 0.9 if len(matched) == 1 else 0.78
    if winner == CaseType.refund_request and len(matched) > 1:
        base = 0.7
    return Classification(winner, base, [f"keyword:{winner.value}"], "rules")
