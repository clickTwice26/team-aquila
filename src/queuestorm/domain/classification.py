"""Rule-based case_type classification.

Classifies from the COMPLAINT text only (evidence_verdict is a separate axis).
Returns a confidence score; when the rules are not confident, the caller may
consult the optional local ML fallback. Phishing/safety always wins the
tie-break so a credential-harvesting message can never be mislabelled.

Each case type carries three keyword layers so English, Bangla-script and
romanized "Banglish" complaints all classify:
  * regex    — English (+ shared) patterns, matched on a lowercased copy
  * banglish — romanized Bangla (vul/bhul, fail holo, dui bar, ferot, ...)
  * bangla   — Bangla-script substrings, matched on the raw text
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
        "banglish": re.compile(
            r"block (hobe|kore dibe|kore dile|hoye jabe)|protar(ok|ona)|"
            r"bkash theke (bol|call|phone|fone)|account block|"
            r"(code|otp|pin) ?(ta)? (chai|chaiteche|dao|den|dite bol|dite bolse)|"
            r"fake (call|sms|message)|sondehojonok",
            re.IGNORECASE,
        ),
        # NOTE: do not add a bare "ফোন দিয়ে" (just "call") — it over-matches
        # benign "please call me" complaints. Keep phishing cues specific.
        "bangla": ["ওটিপি", "পিন", "পাসওয়ার্ড", "ব্লক হবে", "প্রতারক", "প্রতারণা",
                    "থেকে বলছি", "সন্দেহজনক লিংক", "ওটিপি চাইছে", "পিন চাইছে"],
    },
    CaseType.duplicate_payment: {
        # "twice"/"দুইবার"/"dui bar" must co-occur with a charge/deduct verb, so
        # "failed twice" (two failed attempts) is NOT read as a double charge.
        "regex": re.compile(
            r"\bduplicate\b|"
            r"(deducted|charged|debited|taken|cut|paid|went out|gone) .{0,12}(twice|two times)|"
            r"(twice|two times) .{0,12}(deducted|charged|debited|cut|taken)|"
            r"charged (again|two times)|double[- ]billed|two identical|"
            r"both (went through|charged|got charged|got deducted|times|succeeded)|"
            r"(tapped|pressed|clicked) .{0,12}(pay )?again|retr(y|ied) .{0,25}both|"
            r"double (charge|charged|deduct|deducted|payment|debit|bill|amount)|"
            r"same (payment|bill|amount) .{0,15}(twice|two times)|only paid once",
            re.IGNORECASE,
        ),
        "banglish": re.compile(
            r"(kete|kata|katlo|charge|deduct|debit|nise|nilo|niyeche|gese|nei) ?.{0,12}(dui ?bar|duibar|dubar|dui baar)|"
            r"(dui ?bar|duibar|dubar|dui baar) ?.{0,12}(kete|kata|katlo|charge|deduct|nise|nilo|niyeche|gese|hoise|hoye)|"
            r"double (kete|charge|hoise|hoye|bill)|du(i)?tai hoye|duitai hoye gese|"
            r"abar (dilam|dili|dichi) ?.{0,15}(duitai|dui ?bar|both)|ek ?bar (disi|diyechi|dilam|dichi).{0,18}(but|kintu)",
            re.IGNORECASE,
        ),
        "bangla": ["ডবল", "দুইবার কেটে", "দুইবার কাটা", "দুইবার কেটেছে", "দুইবার চার্জ",
                    "দুইবার পেমেন্ট", "দুইবার টাকা", "দুইবার সমান", "দুইবার হয়ে",
                    "দুইবারই হয়ে", "একই পেমেন্ট দুইবার", "দুইবার কনফার্ম",
                    "একবার দিয়েছি কিন্তু", "একবার দিছি"],
    },
    CaseType.wrong_transfer: {
        "regex": re.compile(
            r"wrong (number|person|recipient|account|contact|bkash|digit)|"
            r"sent to (the |a )?wrong|to the wrong (number|person|account|contact)|"
            r"typed (it |the number )?wrong|mistyp|typo|wrong digit|extra digit|"
            r"incorrect (number|recipient|account)|by (mistake|accident)|mistakenly sent|"
            r"wrong.*transfer|selected (the )?wrong|picked (the )?wrong|chose the wrong|"
            r"confused .{0,25}(contact|number|person)|"
            r"(sent|went|transferred) .{0,25}to (a |an |the )?(stranger|unknown|wrong)",
            re.IGNORECASE,
        ),
        "banglish": re.compile(
            r"\bv(?:h)?ul\b|\bbhul\b|\bbhool\b|"
            r"(vul|bhul|bhool|vhul) ?(number|nombor|manush|lok|loke|nam|kore|hoye|jaygay|digit)|"
            r"wrong number e|vule (pathai|diye|chole)|guliye (felsi|fel|gese|felechi)|"
            r"onno (number|account|lok|manush|ekjon) ?.{0,10}(e |er )?(chole|gese|account)|"
            r"(number|digit) vul|extra digit",
            re.IGNORECASE,
        ),
        "bangla": ["ভুল নম্বরে", "ভুল লোকে", "ভুল মানুষ", "ভুল করে পাঠ", "ভুল নাম্বার",
                    "ভুল জায়গায়", "ভুল নম্বর", "ভুল করে", "ভুল হয়ে", "গুলিয়ে",
                    "ডিজিট ভুল", "নম্বর ভুল", "ভুল সেভ", "অন্য নম্বরে", "অন্য একজনের"],
    },
    CaseType.payment_failed: {
        "regex": re.compile(
            r"(transaction|payment|recharge|bill|pay(ment)?|top ?up) .{0,30}"
            r"(failed|unsuccessful|declined|could not be completed|couldn'?t be completed|"
            r"did(n'?t| not) go through|not completed|incomplete)|"
            r"(failed|unsuccessful|declined|could not be completed|did(n'?t| not) go through) "
            r".{0,30}(deduct|balance|taka|cut|charged|money|but)|"
            r"failed but|showed failed|transaction failed|payment failed|recharge failed|"
            r"bill.*failed|failed.*deduct|deduct.*failed|unsuccessful but|declined but|"
            r"no (ticket|recharge|balance) .{0,25}(but|deduct|cut|though)",
            re.IGNORECASE,
        ),
        # Require a fail/deduction co-occurrence so a bare "fail" (e.g. "delivery
        # failed, want a refund") does not hijack this from refund_request.
        "banglish": re.compile(
            r"(transaction|payment|recharge|bill|order) ?.{0,25}(fail|hoy nai|hoy ni|hoyni|hoini|complete hoy nai)|"
            r"(fail|fel) (holo|hoye|hoise|hoye gelo|hoyeche|korse|hoise but)|"
            r"(taka|balance|tk) ?.{0,30}(kete|cut|kome) ?.{0,30}(fail|hoyni|hoy ?ni|hoini|hoy nai|pai ?ni)|"
            r"(recharge|bill|payment|bikash|send|cash ?out) ?.{0,18}(fail|hoyni|hoy ?ni|hoini)|"
            r"pay hoy nai kintu|bill pay hoy nai|recharge ase nai ?.{0,15}(taka|kete)|"
            r"kete (nilo|nise|niyeche|geche|gese) ?.{0,30}(but|kintu) ?.{0,20}(fail|hoyni|pai ?ni)",
            re.IGNORECASE,
        ),
        "bangla": ["ফেইল হয়েছে কিন্তু", "ব্যর্থ", "হয়নি কিন্তু টাকা", "ফেইল কিন্তু",
                    "কেটে নিয়েছে কিন্তু", "টাকা কেটেছে কিন্তু", "হয়নি কিন্তু",
                    "সম্পন্ন হয়নি", "লেনদেন ব্যর্থ", "রিচার্জ ফেইল", "পেমেন্ট ফেইল",
                    "রিচার্জ আসেনি", "ফেইল দেখাল", "ব্যর্থ দেখাল"],
    },
    CaseType.agent_cash_in_issue: {
        "regex": re.compile(
            r"cash[- ]?in|cash[- ]?out|deposited? (through|via|with) (an )?agent|"
            r"\bagent\b.*(balance|money|cash)|agent.*(sent|deposit)|"
            r"balance.*not.*(reflect|come|add)|did(n'?t| not) (get|reflect).*balance",
            re.IGNORECASE,
        ),
        "banglish": re.compile(
            r"cash ?in|cashin|agent er kache|agent ke|agent.{0,18}(taka|cash|deposit|diye)|"
            r"balance e (ase ?nai|ase ?na|aseni|asse na|asy nai)|cash diye(chi|si)",
            re.IGNORECASE,
        ),
        "bangla": ["ক্যাশ ইন", "ক্যাশইন", "এজেন্ট", "ব্যালেন্সে আসেনি", "ব্যালেন্সে টাকা আসেনি"],
    },
    CaseType.merchant_settlement_delay: {
        "regex": re.compile(
            r"settlement|settle(d|ment)? (not|delay)|not settled|payout|"
            r"my sales|merchant .{0,20}(settlement|settle|payout|not (settled|received|credited))|"
            r"sales.*(not|delay)|"
            r"settle .{0,15}(expected|supposed|due|not yet|pending|delayed)|"
            r"(sales|collection) .{0,20}(not settled|not credited|pending|delayed|haven'?t)|"
            r"received .{0,15}(but|yet) .{0,20}(not (settled|credited)|pending)|"
            r"i (run|own|have) (a |my )?(shop|store|business|pharmacy|merchant)",
            re.IGNORECASE,
        ),
        # Avoid bare "merchant" — SAMPLE-04 ("paid a merchant ... refund") must
        # stay refund_request. Require a settlement/payout/sales context.
        "banglish": re.compile(
            r"settlement|bikrir taka|bikri.{0,12}taka|payout|collection ekhono|"
            r"settle (hoyni|hoy ?ni|hoini|hoy nai|hoy nai)|dokan (chala|chalai|er)|"
            r"merchant.{0,15}(settle|payout|taka pai|sale|bikri|collection)|"
            r"collection .{0,15}(ase ?nai|aseni|pending|settle)",
            re.IGNORECASE,
        ),
        "bangla": ["সেটেলমেন্ট", "মার্চেন্ট সেটেল", "বিক্রির টাকা", "পেআউট", "সেটেল হয়নি",
                    "সেটেল হওয়ার", "সেটেল হওয়ার কথা", "রিসিভড দেখাচ্ছে কিন্তু", "কালেকশন",
                    "দোকান চালাই", "বিক্রির টাকা সেটেল"],
    },
    CaseType.refund_request: {
        "regex": re.compile(
            r"\brefund\b|want my money back|changed my mind|don'?t want (it|the product)|"
            r"\breturn\b|cancel(led)? (the |my )?(order|payment)|money back|"
            r"no longer (wish|want|need)|do ?n.?t need (it|this|the)|don'?t need",
            re.IGNORECASE,
        ),
        "banglish": re.compile(
            r"\brefund\b|ferot|ferat|taka ferot|ferot (chai|dao|den|chacchi)|"
            r"money back|order cancel|cancel kor|batil kor|"
            r"mon (bodle|poriborton|change)|pochondo hoy nai|proyojon nei|"
            r"ar (khabo|nibo|lagbe) na",
            re.IGNORECASE,
        ),
        "bangla": ["রিফান্ড", "টাকা ফেরত চাই", "মন বদল", "মন পরিবর্তন", "পণ্য চাই না",
                    "ফেরত দিন", "প্রয়োজন নেই", "আর খাব না", "অর্ডার বাতিল", "আর নিব না",
                    "পছন্দ হয়নি"],
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


# A money-send verb (EN + Bangla + romanized) — used to detect "sent X but not
# received", a transfer dispute even without an explicit "wrong" keyword.
_SEND_RE = re.compile(
    r"\bsent\b|\bsend\b|\btransfer(?:red|ring)?\b|পাঠ|"
    r"patha(i|isi|ichi|ilam|ye|iye|lam|si)",
    re.IGNORECASE,
)


def _hits(signals: ComplaintSignals, spec: dict) -> bool:
    if spec["regex"].search(signals.lower):
        return True
    if "banglish" in spec and spec["banglish"].search(signals.lower):
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
