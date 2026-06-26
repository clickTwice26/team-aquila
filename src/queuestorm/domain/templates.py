"""Deterministic, safe, multilingual text builders.

Produces agent_summary (internal, English), recommended_next_action (internal,
English) and customer_reply (customer-facing, mirrors the complaint language).
Every customer_reply is safe BY CONSTRUCTION; the safety filter runs afterwards
as a second, independent guarantee.
"""
from __future__ import annotations

from ..schemas.enums import CaseType, Department, EvidenceVerdict
from .matching import Transaction

PIN_REMINDER_EN = "Please do not share your PIN or OTP with anyone."
PIN_REMINDER_BN = "অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"


def reply_language(language: str, raw: str) -> str:
    """Reply in Bangla when the complaint is Bangla; English otherwise."""
    if language == "bn":
        return "bn"
    if language == "mixed" and any("ঀ" <= ch <= "৿" for ch in raw):
        return "bn"
    return "en"


# --------------------------------------------------------------------------- #
# customer_reply
# --------------------------------------------------------------------------- #
def _reply_en(case_type: CaseType, txn: str | None, has_txn: bool) -> str:
    t = txn or "the transaction"
    if case_type == CaseType.phishing_or_social_engineering:
        return ("Thank you for reaching out before sharing any information. We never ask for "
                "your PIN, OTP, or password under any circumstances. Please do not share these "
                "with anyone, even if they claim to be from us. Our fraud team has been notified "
                "of this incident.")
    if case_type == CaseType.wrong_transfer and not has_txn:
        return ("Thank you for reaching out. We see more than one transaction that could match "
                "your description. Could you share the recipient's number so we can identify the "
                f"right transaction? {PIN_REMINDER_EN}")
    if case_type == CaseType.wrong_transfer:
        return (f"We have noted your concern about transaction {t}. Our dispute resolution team "
                f"will review the case and contact you through official support channels. {PIN_REMINDER_EN}")
    if case_type == CaseType.payment_failed:
        return (f"We have noted that transaction {t} may have caused an unexpected balance "
                "deduction. Our payments team will review the case and any eligible amount will be "
                f"returned through official channels. {PIN_REMINDER_EN}")
    if case_type == CaseType.duplicate_payment:
        return (f"We have noted the possible duplicate payment for transaction {t}. Our payments "
                "team will verify with the biller and any eligible amount will be returned through "
                f"official channels. {PIN_REMINDER_EN}")
    if case_type == CaseType.refund_request:
        return ("Thank you for reaching out. Refunds for completed merchant payments depend on the "
                "merchant's own policy. We recommend contacting the merchant directly. If you need "
                f"help reaching them, please reply and we will guide you. {PIN_REMINDER_EN}")
    if case_type == CaseType.merchant_settlement_delay:
        return (f"We have noted your concern about settlement {t}. Our merchant operations team "
                "will check the batch status and update you on the expected settlement time "
                "through official channels.")
    if case_type == CaseType.agent_cash_in_issue:
        return (f"We have noted your concern about transaction {t}. Our agent operations team will "
                f"verify it and update you through official support channels. {PIN_REMINDER_EN}")
    return ("Thank you for reaching out. To help you faster, please share the transaction ID, the "
            f"amount involved, and a short description of what went wrong. {PIN_REMINDER_EN}")


def _reply_bn(case_type: CaseType, txn: str | None, has_txn: bool) -> str:
    t = txn or "সংশ্লিষ্ট লেনদেন"
    if case_type == CaseType.phishing_or_social_engineering:
        return ("কোনো তথ্য শেয়ার করার আগে যোগাযোগ করার জন্য ধন্যবাদ। আমরা কখনোই আপনার পিন, ওটিপি বা "
                "পাসওয়ার্ড চাই না। কেউ আমাদের পরিচয় দিলেও এগুলো কারো সাথে শেয়ার করবেন না। আমাদের ফ্রড "
                "দলকে বিষয়টি জানানো হয়েছে।")
    if case_type == CaseType.wrong_transfer and not has_txn:
        return ("যোগাযোগ করার জন্য ধন্যবাদ। একই বিবরণের সাথে মেলে এমন একাধিক লেনদেন দেখা যাচ্ছে। সঠিক "
                f"লেনদেনটি শনাক্ত করতে অনুগ্রহ করে প্রাপকের নম্বরটি জানান। {PIN_REMINDER_BN}")
    if case_type == CaseType.wrong_transfer:
        return (f"আপনার লেনদেন {t} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের ডিসপিউট দল বিষয়টি যাচাই করে "
                f"অফিসিয়াল সাপোর্ট চ্যানেলের মাধ্যমে আপনার সাথে যোগাযোগ করবে। {PIN_REMINDER_BN}")
    if case_type == CaseType.payment_failed:
        return (f"লেনদেন {t} এর কারণে আপনার ব্যালেন্স থেকে টাকা কেটে থাকতে পারে বলে আমরা অবগত হয়েছি। "
                "আমাদের পেমেন্টস দল বিষয়টি যাচাই করবে এবং প্রযোজ্য কোনো অর্থ অফিসিয়াল চ্যানেলের মাধ্যমে "
                f"ফেরত দেওয়া হবে। {PIN_REMINDER_BN}")
    if case_type == CaseType.duplicate_payment:
        return (f"লেনদেন {t} এ সম্ভাব্য দ্বৈত পেমেন্টের বিষয়ে আমরা অবগত হয়েছি। আমাদের পেমেন্টস দল যাচাই "
                f"করবে এবং প্রযোজ্য কোনো অর্থ অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে। {PIN_REMINDER_BN}")
    if case_type == CaseType.refund_request:
        return ("যোগাযোগ করার জন্য ধন্যবাদ। সম্পন্ন হওয়া মার্চেন্ট পেমেন্টের রিফান্ড মার্চেন্টের নিজস্ব "
                "নীতিমালার উপর নির্ভর করে। আমরা সরাসরি মার্চেন্টের সাথে যোগাযোগ করার পরামর্শ দিচ্ছি। "
                f"{PIN_REMINDER_BN}")
    if case_type == CaseType.merchant_settlement_delay:
        return (f"সেটেলমেন্ট {t} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের মার্চেন্ট অপারেশন্স দল ব্যাচের অবস্থা "
                "যাচাই করে অফিসিয়াল চ্যানেলের মাধ্যমে আপনাকে জানাবে।")
    if case_type == CaseType.agent_cash_in_issue:
        return (f"আপনার লেনদেন {t} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত যাচাই "
                f"করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। {PIN_REMINDER_BN}")
    return ("যোগাযোগ করার জন্য ধন্যবাদ। আমরা দ্রুত সাহায্য করতে চাই — অনুগ্রহ করে লেনদেন আইডি, পরিমাণ "
            f"এবং সমস্যাটি কী তা জানান। {PIN_REMINDER_BN}")


def build_customer_reply(case_type: CaseType, language: str, raw: str, txn: str | None) -> str:
    has_txn = txn is not None
    if reply_language(language, raw) == "bn":
        return _reply_bn(case_type, txn, has_txn)
    return _reply_en(case_type, txn, has_txn)


# --------------------------------------------------------------------------- #
# agent_summary (internal, English) — names the txn, amount and the conflict.
# --------------------------------------------------------------------------- #
def build_agent_summary(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    txn: Transaction | None,
    amount: float | None,
    user_type: str | None,
) -> str:
    amt = (f"{int(amount)} BDT" if amount and float(amount).is_integer()
           else (f"{amount} BDT" if amount else "an unspecified amount"))
    tid = txn.transaction_id if txn else None
    actor = "Merchant" if user_type == "merchant" else ("Agent" if user_type == "agent" else "Customer")

    if case_type == CaseType.phishing_or_social_engineering:
        return ("Customer reports an unsolicited contact asking for credentials (likely social "
                "engineering). No transaction in scope; treat as a fraud/safety report.")
    if case_type == CaseType.wrong_transfer and tid and verdict == EvidenceVerdict.inconsistent:
        return (f"{actor} claims {tid} ({amt}) was a wrong transfer, but the history shows prior "
                "completed transfers to the same recipient, suggesting an established counterparty.")
    if case_type == CaseType.wrong_transfer and tid:
        return f"{actor} reports sending {amt} via {tid} to the wrong recipient and seeks help recovering it."
    if case_type == CaseType.wrong_transfer:
        return (f"{actor} reports a wrong transfer of {amt}, but multiple transactions plausibly "
                "match and none can be uniquely identified without more detail.")
    if case_type == CaseType.payment_failed and tid:
        return (f"{actor} attempted a {amt} payment ({tid}) which failed but reports the balance "
                "was deducted. Needs payments operations review.")
    if case_type == CaseType.duplicate_payment and tid:
        return (f"{actor} reports a duplicate {amt} payment; two near-identical charges exist and "
                f"{tid} is the suspected duplicate.")
    if case_type == CaseType.merchant_settlement_delay and tid:
        return (f"Merchant reports {amt} settlement ({tid}) delayed beyond the expected window; "
                "settlement status is pending.")
    if case_type == CaseType.agent_cash_in_issue and tid:
        return (f"{actor} reports {amt} cash-in ({tid}) not reflected in balance; transaction is "
                "pending. Needs agent operations verification.")
    if case_type == CaseType.refund_request and tid:
        return (f"{actor} requests a refund of {amt} for {tid}; appears to be a change-of-mind "
                "rather than a service failure.")
    if case_type == CaseType.refund_request:
        return f"{actor} requests a refund of {amt}; original transaction not clearly identified."
    return (f"{actor} reports a concern without enough detail to identify a specific transaction. "
            "Clarification required.")


# --------------------------------------------------------------------------- #
# recommended_next_action (internal, English) — verb-led, safe.
# --------------------------------------------------------------------------- #
def build_next_action(
    case_type: CaseType,
    verdict: EvidenceVerdict,
    txn: str | None,
    department: Department,
) -> str:
    t = txn or "the transaction"
    if case_type == CaseType.phishing_or_social_engineering:
        return ("Escalate to the fraud_risk team immediately. Reassure the customer that the "
                "company never asks for OTP/PIN, and log the reported contact for fraud-pattern "
                "analysis.")
    if case_type == CaseType.wrong_transfer and verdict == EvidenceVerdict.inconsistent:
        return ("Flag for human review. Verify with the customer whether this was genuinely a wrong "
                "transfer given the established pattern with this recipient before opening a dispute.")
    if case_type == CaseType.wrong_transfer and txn is None:
        return ("Ask the customer for the recipient's number to identify the correct transaction. "
                "Do not open a dispute until the transaction is confirmed.")
    if case_type == CaseType.wrong_transfer:
        return f"Verify {t} details with the customer and initiate the wrong-transfer dispute workflow per policy."
    if case_type == CaseType.payment_failed:
        return (f"Investigate the ledger status of {t}. If the balance was deducted on a failed "
                "payment, initiate the standard reversal flow within SLA.")
    if case_type == CaseType.duplicate_payment:
        return (f"Verify the duplicate with payments_ops. If the biller confirms a single charge, "
                f"initiate reversal of {t} per policy.")
    if case_type == CaseType.merchant_settlement_delay:
        return (f"Route to merchant_operations to verify the settlement batch status for {t} and "
                "communicate a revised ETA if delayed.")
    if case_type == CaseType.agent_cash_in_issue:
        return (f"Investigate the pending status of {t} with agent operations and resolve within "
                "the standard cash-in SLA.")
    if case_type == CaseType.refund_request:
        return ("Inform the customer that refund eligibility depends on the merchant's policy and "
                "guide them on contacting the merchant directly.")
    return ("Reply to the customer requesting specifics: which transaction, what amount, what went "
            "wrong, and the approximate time.")
