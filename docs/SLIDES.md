<!--
  QueueStorm Investigator — 4-slide presentation deck (Team Aquila).
  HOW TO PRESENT:
    • GitHub: push and open this file — Mermaid renders natively. Each "---" is a slide.
    • VS Code: install "Markdown Preview Mermaid Support", open preview (Ctrl/Cmd+Shift+V), full-screen it.
    • Scroll one slide per screen while recording. Diagrams are trimmed to fit a 16:9 frame.
  Covers the four required topics: architecture · API flow · AI/model usage · safety logic.
-->

# 🛰️ QueueStorm Investigator
### Team Aquila · An evidence-grounded support copilot for digital finance

> Reads **one complaint + recent transactions** → returns **one structured JSON verdict**.
> Not a complaint *classifier* — a complaint **investigator**: the complaint says one thing, the data
> may say another, and the service decides **what is actually true**.

<sub>4 slides · Architecture → API Flow → AI/Model Usage → Safety</sub>

---

## 1️⃣ Solution Architecture — a *rules-first hybrid*

```mermaid
flowchart TB
    C([🌐 Client · Judge harness]) --> API

    subgraph API [" 🌐 API shell — FastAPI (async, tolerant parse) "]
        H["GET /health<br/><i>static</i>"]
        A["POST /analyze-ticket"]
    end

    API --> CORE

    subgraph CORE [" 🧠 Pure deterministic domain core — zero web / ML deps "]
        direction LR
        N[normalize] --> CL[classify] --> M[match] --> R[route] --> T[draft] --> S["🛡️ safety"]
    end

    CORE --> SCH[["📐 Pydantic StrEnums → response_model"]]
    ML["🤖 optional 80 KB ML fallback"] -. side · never decides a scored field .-> CORE

    style CORE fill:#eef7ff,stroke:#3b82f6,stroke-width:1px
    style S fill:#fee2e2,stroke:#ef4444,stroke-width:2px
    style ML fill:#fef9c3,stroke:#eab308,stroke-dasharray:4 3
    style SCH fill:#ede9fe,stroke:#8b5cf6
```

**📌 What this shows**
- A thin **async FastAPI** edge wraps a **pure, deterministic domain core** — the core imports *nothing*
  from the web or ML layers, so it’s fast, reproducible, and unit-testable in isolation.
- The **rule engine is the single source of truth** for all **six auto-scored fields**.
- **Pydantic `StrEnum`s** make emitting an invalid enum *impossible* — free schema correctness.
- The ML model sits **on the side**: an optional assist that can never decide a scored field.
  **$0, fully offline, no quota risk.**

<sub>Team Aquila · QueueStorm Investigator · 1 / 4</sub>

---

## 2️⃣ API Flow — the 8-stage investigation pipeline

```mermaid
flowchart LR
    IN([complaint + transactions]) --> P1["parse +<br/>normalize"]
    P1 --> P2["classify case_type<br/><b>from the complaint</b>"]
    P2 --> P3["match<br/>transaction"]
    P3 --> P4["judge evidence_verdict<br/><b>from the data</b>"]
    P4 --> P5["route dept ·<br/>severity ·<br/>human review"]
    P5 --> P6["draft<br/>text"]
    P6 --> P7[/"🛡️ safety filter<br/>(runs last)"/]
    P7 --> OUT([✅ structured JSON verdict])

    style P2 fill:#eef7ff,stroke:#3b82f6
    style P4 fill:#eef7ff,stroke:#3b82f6
    style P7 fill:#fee2e2,stroke:#ef4444,stroke-width:2px
    style OUT fill:#dcfce7,stroke:#22c55e
```

**📌 What this shows**
- Two endpoints only: a **static `/health`** (ready in well under 60 s) and **`POST /analyze-ticket`**,
  which runs this **deterministic 8-stage pipeline** in **~1–5 ms** (p95 ≈ 20 ms, no network).
- `case_type` is decided **from the complaint**; `evidence_verdict` is decided **from the transaction
  data** — two **independent axes**.
- When the evidence is genuinely ambiguous, it returns **`null` + `insufficient_data`** and asks for
  clarification — **honest uncertainty instead of a confident guess**.
- The service **never crashes**: bad input → controlled `400 / 422`, internal error → generic `500`,
  `ticket_id` always echoed.

<sub>Team Aquila · QueueStorm Investigator · 2 / 4</sub>

---

## 3️⃣ AI / Model Usage — rules decide, the model only assists

```mermaid
flowchart TD
    R["rule classifier<br/>(keywords · EN/BN/Banglish)"] --> Q1{"confident ≥ 0.6<br/>or phishing?"}
    Q1 -- yes --> USE["✅ use the RULES<br/><b>source of truth</b>"]
    Q1 -- no --> Q2{"optional ML<br/>enabled?"}
    Q2 -- no --> USE
    Q2 -- yes --> ML["🤖 80 KB scikit-learn<br/>TF-IDF + Logistic Regression"]
    ML --> Q3{"confident AND not<br/>weak-signal fraud?"}
    Q3 -- no --> USE
    Q3 -- yes --> ADOPT["adopt ML label<br/>(robustness hedge only)"]

    style USE fill:#dcfce7,stroke:#22c55e,stroke-width:2px
    style ML fill:#fef9c3,stroke:#eab308
    style ADOPT fill:#fef9c3,stroke:#eab308
```

**📌 What this shows**
- **No LLM in the judged path.** Every scored field and every safety guarantee is pure code.
- A tiny **80 KB local classifier** (in-process, CPU, sub-millisecond, **no network**) is consulted
  **only** when the rules are *unsure* — a hedge for unusual phrasings.
- **Guard-railed:** it can **never override a phishing/safety label** and **never decides a scored
  field** — at most it nudges the *prose*.
- Result: an ML or LLM outage **degrades quality, never availability** — and the cost is **$0**.

<sub>Team Aquila · QueueStorm Investigator · 3 / 4</sub>

---

## 4️⃣ Safety Logic — a deterministic filter on the wire

```mermaid
flowchart TD
    T([any generated reply / next-action]) --> AUD["audit EN + BN<br/>(mask known-safe phrases first)"]
    AUD --> P2["<b>P2</b> → rewrite refund / reversal / unlock promises<br/>→ 'any eligible amount via official channels'"]
    P2 --> P3["<b>P3</b> → strip phone numbers, URLs, 'call that number'<br/>→ 'contact our official support channels'"]
    P3 --> P1["<b>P1</b> → drop any sentence that REQUESTS a credential"]
    P1 --> REM["append PIN / OTP reminder<br/>in the complaint's language"]
    REM --> Q{"still unsafe?"}
    Q -- yes --> FB["canned safe fallback template"]
    Q -- no --> OK["✅ guaranteed-safe text leaves the service"]
    FB --> OK

    style P1 fill:#fee2e2,stroke:#ef4444
    style P2 fill:#fee2e2,stroke:#ef4444
    style P3 fill:#fee2e2,stroke:#ef4444
    style OK fill:#dcfce7,stroke:#22c55e,stroke-width:2px
```

**📌 What this shows**
- A **code-level filter runs LAST** on every `customer_reply` and `recommended_next_action` — even a
  jailbroken model **cannot put an unsafe string on the wire**.
- **P1** never asks for PIN/OTP/password/card *(−15)* · **P2** never promises a refund/reversal/unlock
  *(−10)* · **P3** never directs to a suspicious third party *(−10)*.
- The **credential-safety reminder** is appended **programmatically in the complaint’s language**, so
  it can never be dropped.
- Prompt-injection in the complaint is treated as **untrusted data, never instructions**.

> ✅ **Proof:** 10 / 10 public sample cases match · **92 automated tests pass** · deployed & live.

<sub>Team Aquila · QueueStorm Investigator · 4 / 4</sub>
