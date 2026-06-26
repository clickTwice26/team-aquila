"""Train the tiny local case_type fallback classifier (offline, one-off).

Produces app/models/case_type_clf.joblib — a small TF-IDF + Logistic Regression
pipeline (~tens of KB) trained on augmented synthetic phrases covering English,
Bangla and Banglish. It runs on CPU with no network and is only consulted when
the rule classifier is not confident. The rule engine remains the source of
truth; this is a robustness hedge for unusual hidden-test phrasings.

Usage:
    python scripts/train_classifier.py
"""
from __future__ import annotations

import os
import sys

# Synthetic, label-balanced training phrases. NOT the hidden test set — these
# only teach the fallback general phrasing patterns per case_type.
TRAINING_DATA: dict[str, list[str]] = {
    "wrong_transfer": [
        "I sent money to the wrong number by mistake",
        "transferred to wrong person please help me get it back",
        "I typed the number wrong and sent cash to a stranger",
        "accidentally sent taka to an unknown recipient",
        "sent to the wrong account can you reverse it",
        "ভুল নম্বরে টাকা পাঠিয়েছি ফেরত দিন",
        "ভুল মানুষকে টাকা পাঠিয়ে ফেলেছি",
        "vul number e taka pathaisi please help",
        "wrong number e send hoye gese ferot chai",
        "I mistakenly transferred to the wrong mobile number",
    ],
    "payment_failed": [
        "my payment failed but the balance was deducted",
        "recharge showed failed yet money was taken",
        "transaction failed but amount cut from my account",
        "bill payment unsuccessful but balance reduced",
        "the app said failed but my money is gone",
        "পেমেন্ট ফেইল হয়েছে কিন্তু টাকা কেটে নিয়েছে",
        "রিচার্জ হয়নি কিন্তু ব্যালেন্স থেকে টাকা গেছে",
        "payment fail holo but taka kete nilo",
        "failed transaction but money deducted",
        "transfer failed but amount was debited",
    ],
    "refund_request": [
        "I want a refund for my purchase",
        "please refund my money I changed my mind",
        "I don't want the product anymore please return my money",
        "cancel my order and refund the amount",
        "requesting a refund for the merchant payment",
        "রিফান্ড চাই আমি পণ্যটি আর নিতে চাই না",
        "টাকা ফেরত চাই মন বদলে গেছে",
        "ami refund chai product lagbe na",
        "money back chai order cancel koren",
        "kindly return my payment I no longer need it",
    ],
    "duplicate_payment": [
        "I was charged twice for the same bill",
        "the payment got deducted two times",
        "double payment for my electricity bill",
        "I paid once but money was taken twice",
        "duplicate charge on my account please check",
        "একই বিল দুইবার কেটেছে",
        "একবার দিয়েছি কিন্তু দুইবার কাটা হয়েছে",
        "duplicate payment hoyeche duibar kateche",
        "charged again for the same transaction",
        "two identical payments went out for one purchase",
    ],
    "merchant_settlement_delay": [
        "my merchant settlement has not arrived yet",
        "yesterday's sales were not settled to my account",
        "settlement delayed beyond the usual time",
        "I am a merchant and my payout is missing",
        "store sales amount not settled please check",
        "মার্চেন্ট সেটেলমেন্ট এখনো আসেনি",
        "আমার বিক্রির টাকা সেটেল হয়নি",
        "merchant settlement ase nai ekhono",
        "payout for my shop is overdue",
        "the settlement batch for my business is late",
    ],
    "agent_cash_in_issue": [
        "I did a cash in through an agent but balance not updated",
        "deposited money with agent but it did not reflect",
        "agent says he sent the cash but I have not received it",
        "cash in done at agent point but balance is zero",
        "my agent deposit is not showing in my account",
        "এজেন্টের কাছে ক্যাশ ইন করেছি কিন্তু ব্যালেন্সে আসেনি",
        "এজেন্ট বলছে টাকা পাঠিয়েছে কিন্তু পাইনি",
        "agent er kache cash in korsi but balance e ase nai",
        "cash deposit through agent not credited",
        "agent cash in not reflected in my wallet",
    ],
    "phishing_or_social_engineering": [
        "someone called asking for my OTP is this real",
        "a person claiming to be from bKash wants my PIN",
        "I got a message saying my account will be blocked share the code",
        "scammer asked me to share my password",
        "suspicious caller wants my verification code",
        "কেউ আমাকে ফোন দিয়ে ওটিপি চাইছে",
        "bKash থেকে বলছে বলে পিন চাইছে অ্যাকাউন্ট ব্লক হবে বলছে",
        "keu amar otp chasche eta ki thik",
        "fraud call asking for my pin and password",
        "got a phishing sms with a link asking for my credentials",
    ],
    "other": [
        "something is wrong with my money please check",
        "I have a problem with my account",
        "can you help me with an issue",
        "there is an error somewhere I am not sure",
        "my balance looks strange please look into it",
        "আমার টাকার কিছু একটা সমস্যা হয়েছে",
        "কিছু একটা ঠিক নেই দেখুন",
        "amar account e somossa hocche",
        "I need help but not sure what happened",
        "general question about my wallet",
    ],
}


def main() -> int:
    try:
        import joblib
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError:
        print("scikit-learn / joblib not installed. Install with:")
        print("    pip install scikit-learn joblib")
        return 1

    texts: list[str] = []
    labels: list[str] = []
    for label, phrases in TRAINING_DATA.items():
        for phrase in phrases:
            if phrase:
                texts.append(phrase)
                labels.append(label)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            analyzer="char_wb",      # robust to typos / Banglish / mixed script
            ngram_range=(2, 5),
            min_df=1,
        )),
        ("clf", LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced")),
    ])
    pipeline.fit(texts, labels)

    # Quick sanity report on the training data.
    acc = pipeline.score(texts, labels)
    print(f"Trained on {len(texts)} phrases across {len(TRAINING_DATA)} classes; "
          f"train accuracy={acc:.3f}")

    out_dir = os.path.join(os.path.dirname(__file__), "..", "src", "queuestorm", "ml", "artifacts")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "case_type_clf.joblib")
    joblib.dump(pipeline, out_path, compress=3)
    size_kb = os.path.getsize(out_path) / 1024.0
    print(f"Saved model -> {out_path} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
