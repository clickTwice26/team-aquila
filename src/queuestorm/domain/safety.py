"""Deterministic OUTPUT SAFETY FILTER — the real guardrail.

Runs LAST on every customer_reply and recommended_next_action, regardless of
who wrote them. Guarantees, on every response:
  * no credential REQUEST (PIN/OTP/password/card/CVV) survives           (P1, -15)
  * no unauthorized financial CONFIRMATION survives (refund/reversal...)  (P2, -10)
  * no suspicious third-party direction / copied phone/URL survives       (P3, -10)
  * no system-prompt/secret fragment leaks
  * the credential-safety reminder is present in the right language
If a reply cannot be made safe, it is replaced with a canned safe template.
"""
from __future__ import annotations

import re

from ..schemas.enums import CaseType
from .templates import PIN_REMINDER_BN, PIN_REMINDER_EN, reply_language

SAFE_RETURN = "any eligible amount will be returned through official channels"
SAFE_CHANNEL = "please contact our official support channels"

_SAFE_PHRASES = [
    "do not share your pin or otp with anyone",
    "do not share these with anyone",
    "never ask for your pin, otp, or password",
    "never ask for your pin",
    "we never ask for your",
    "পিন বা ওটিপি শেয়ার করবেন না",
    "পিন, ওটিপি বা পাসওয়ার্ড চাই না",
    "এগুলো কারো সাথে শেয়ার করবেন না",
]

# P1: credential REQUESTS.
_P1_EN = re.compile(
    r"\b(?:share|enter|provide|give|send|tell|type|confirm|verify|submit|reveal|"
    r"need|ask for|provide us|send us)\b[^.?!]{0,40}\b"
    r"(?:pin|otp|password|passcode|cvv|card\s*number|security\s*code|credential)s?\b",
    re.IGNORECASE,
)
_P1_BN = re.compile(r"(?:পিন|ওটিপি|পাসওয়ার্ড|গোপন নম্বর|কার্ড নম্বর)[^।?!]{0,40}?"
                    r"(?:দিন|দাও|শেয়ার কর|বলুন|লিখুন|পাঠান|জানান)")

# P2: unauthorized financial CONFIRMATIONS.
_P2_PATTERNS = [
    re.compile(r"\bwe(?:'ve| have| will| shall)?\s+(?:already\s+)?"
               r"(?:refund(?:ed)?|reverse[d]?|credit(?:ed)?|return(?:ed)?)\b[^.?!]*", re.IGNORECASE),
    re.compile(r"\byour\s+(?:refund|money|amount|balance)\s+(?:is|has been|will be|will get)\s+"
               r"(?:processed|approved|reversed|returned|credited|refunded|guaranteed)\b[^.?!]*", re.IGNORECASE),
    re.compile(r"\b(?:account|your account)\b[^.?!]{0,30}(?:has been|will be|is)\s+"
               r"(?:unlocked|unblocked|restored|recovered|reactivated)\b[^.?!]*", re.IGNORECASE),
    re.compile(r"\bwe\s+(?:approve|authori[sz]e|guarantee)\b[^.?!]*", re.IGNORECASE),
    re.compile(r"(?:ফেরত|রিফান্ড)[^।?!]{0,20}(?:দেওয়া হয়েছে|দিয়ে দিয়েছি|দেব|নিশ্চিত|হয়ে গেছে)"),
]

# P3: third-party direction / copied contact.
_P3_DIRECTION = re.compile(
    r"\b(?:call|contact|dial|reply to|message|text|whatsapp)\b[^.?!]{0,30}"
    r"\b(?:this|that|the)\b[^.?!]{0,15}\b(?:number|caller|sms|link|person|agent)\b",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?:\+?880\d{8,11}|\b01\d{8,9}\b|\b\d{11,}\b)")
_URL = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|xyz|info|link)\b", re.IGNORECASE)

# Injection / secret leakage.
_LEAK = re.compile(
    r"\b(?:system prompt|ignore (?:previous|above) instructions|api[_\s-]?key)\b|sk-[A-Za-z0-9]{6,}",
    re.IGNORECASE,
)

_SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+")


def _mask_safe(text: str) -> str:
    low = text.lower()
    for phrase in _SAFE_PHRASES:
        low = low.replace(phrase, " " * len(phrase))
    return low


def audit(text: str) -> list[str]:
    """Return the violation codes present in `text` (after safe-masking)."""
    masked = _mask_safe(text)
    found: list[str] = []
    if _P1_EN.search(masked) or _P1_BN.search(masked):
        found.append("P1_credential_request")
    for pat in _P2_PATTERNS:
        if pat.search(text):
            found.append("P2_unauthorized_confirmation")
            break
    if _P3_DIRECTION.search(text) or _PHONE.search(text) or _URL.search(text):
        found.append("P3_third_party_direction")
    if _LEAK.search(text):
        found.append("leak_or_injection")
    return found


def is_safe(text: str) -> bool:
    return not audit(text)


def _sanitize(text: str) -> str:
    if not text:
        return text
    for pat in _P2_PATTERNS:
        text = pat.sub(SAFE_RETURN, text)
    text = _P3_DIRECTION.sub(SAFE_CHANNEL, text)
    text = _PHONE.sub("our official support channels", text)
    text = _URL.sub("our official support channels", text)
    text = _LEAK.sub("", text)
    kept = []
    for sentence in _SENT_SPLIT.split(text):
        masked = _mask_safe(sentence)
        if _P1_EN.search(masked) or _P1_BN.search(masked):
            continue
        kept.append(sentence)
    text = " ".join(s.strip() for s in kept if s.strip())
    return re.sub(r"\s{2,}", " ", text).strip()


def _ensure_reminder(reply: str, language: str, raw: str, case_type: CaseType) -> str:
    if case_type == CaseType.merchant_settlement_delay:
        return reply
    # Already contains a credential-safety reminder (any phrasing/language)?
    if "do not share" in reply.lower() or "শেয়ার করবেন না" in reply:
        return reply
    lang = reply_language(language, raw)
    reminder = PIN_REMINDER_BN if lang == "bn" else PIN_REMINDER_EN
    sep = "" if not reply else " "
    return f"{reply}{sep}{reminder}".strip()


def _safe_fallback(language: str, raw: str) -> str:
    if reply_language(language, raw) == "bn":
        return ("যোগাযোগ করার জন্য ধন্যবাদ। আমাদের দল বিষয়টি যাচাই করে অফিসিয়াল সাপোর্ট চ্যানেলের "
                "মাধ্যমে আপনার সাথে যোগাযোগ করবে।")
    return ("Thank you for reaching out. Our team will review your case and contact you through "
            "official support channels.")


def enforce(
    customer_reply: str,
    recommended_next_action: str,
    language: str,
    raw: str,
    case_type: CaseType,
) -> tuple[str, str, list[str]]:
    """Return (safe_reply, safe_next_action, violation_codes_detected)."""
    flags = sorted(set(audit(customer_reply) + audit(recommended_next_action)))

    reply = _sanitize(customer_reply)
    next_action = _sanitize(recommended_next_action)
    reply = _ensure_reminder(reply, language, raw, case_type)

    if audit(reply):
        reply = _ensure_reminder(_safe_fallback(language, raw), language, raw, case_type)
    if audit(next_action):
        next_action = ("Escalate to the appropriate team for manual review through official "
                       "internal channels.")
    return reply, next_action, flags
