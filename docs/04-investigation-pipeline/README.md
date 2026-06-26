# 04 · 🔬 The Investigation Pipeline

[◀ API Contract](../03-api-contract/README.md) · [🏠 Docs Home](../README.md) · [Next ▶ Normalization](../05-normalization/README.md)

---

The pipeline is the **orchestrator** that turns a parsed ticket into a verdict. It is implemented as
a deterministic state machine in
[`domain/investigator.py`](../../src/queuestorm/domain/investigator.py) and runs the stages in this
**exact order**:

```text
parse → classify case_type → match transaction → judge evidence_verdict
      → route department → set severity → set human_review_required
      → draft text → enforce safety
```

> **Why order matters:** `case_type` is classified *before* matching so that phishing/safety cases
> short-circuit (they often have empty history). The safety filter runs *last* so nothing unsafe can
> escape — regardless of who wrote the text.

---

## 🏃 Activity diagram — end-to-end flow

```mermaid
flowchart TD
    start([ParsedTicket]) --> sig["① build_signals()<br/>normalize complaint"]
    sig --> cls["② _final_classification()<br/>rules (+ optional ML)"]
    cls --> match["③ match()<br/>relevant_transaction_id"]
    match --> verdict["④ evidence_verdict<br/>(decided inside match)"]
    verdict --> dept["⑤ route_department()"]
    dept --> sev["⑥ assess_severity()"]
    sev --> hr["⑦ needs_human_review()"]
    hr --> txt["⑧ draft text<br/>summary · next_action · reply"]
    txt --> safe[/"⑨ safety.enforce()"/]
    safe --> conf["compute confidence<br/>+ reason_codes"]
    conf --> resp([AnalyzeResponse · 200])

    style cls fill:#eef7ff,stroke:#3b82f6
    style match fill:#eef7ff,stroke:#3b82f6
    style verdict fill:#eef7ff,stroke:#3b82f6
    style dept fill:#eef7ff,stroke:#3b82f6
    style sev fill:#eef7ff,stroke:#3b82f6
    style hr fill:#eef7ff,stroke:#3b82f6
    style safe fill:#fee2e2,stroke:#ef4444,stroke-width:2px
    style resp fill:#dcfce7,stroke:#22c55e
```

The blue stages produce the **six auto-scored fields**; the red stage is the **independent safety
guarantee**.

---

## 🔁 Sequence diagram — module collaboration

```mermaid
sequenceDiagram
    autonumber
    participant IN as investigator._investigate
    participant NO as normalization
    participant CL as classification
    participant ML as ml.classifier
    participant MA as matching
    participant RO as routing
    participant TE as templates
    participant SA as safety

    IN->>NO: build_signals(complaint, language)
    NO-->>IN: ComplaintSignals
    IN->>CL: classify_rules(signals)
    CL-->>IN: Classification (case_type, confidence)
    opt rule confidence < 0.6 and not phishing
        IN->>ML: predict(raw)
        ML-->>IN: (label, proba) or None
    end
    IN->>MA: match(signals, case_type, transactions)
    MA-->>IN: MatchResult (rel_id, evidence_verdict)
    IN->>RO: route_department / assess_severity / needs_human_review
    RO-->>IN: department, severity, human_review
    IN->>TE: build_agent_summary / next_action / customer_reply
    TE-->>IN: draft strings
    IN->>SA: enforce(reply, next_action, language, raw, case_type)
    SA-->>IN: safe reply, safe next_action, flags
    IN-->>IN: assemble AnalyzeResponse
```

---

## Stage-by-stage reference

| # | Stage | Function | Chapter |
|:-:|-------|----------|---------|
| ① | Normalize | `build_signals()` | [05 · Normalization](../05-normalization/README.md) |
| ② | Classify case_type | `_final_classification()` → `classify_rules()` (+ ML) | [06 · Classification](../06-classification/README.md) |
| ③ | Match transaction | `match()` → `relevant_transaction_id` | [07 · Evidence Matching](../07-evidence-matching/README.md) |
| ④ | Judge verdict | inside `match()` → `evidence_verdict` | [07 · Evidence Matching](../07-evidence-matching/README.md) |
| ⑤ | Route department | `route_department()` | [08 · Routing & Severity](../08-routing-and-severity/README.md) |
| ⑥ | Set severity | `assess_severity()` | [08 · Routing & Severity](../08-routing-and-severity/README.md) |
| ⑦ | Human review | `needs_human_review()` | [08 · Routing & Severity](../08-routing-and-severity/README.md) |
| ⑧ | Draft text | `build_*` in `templates.py` | [10 · Text Generation](../10-text-generation/README.md) |
| ⑨ | Enforce safety | `safety.enforce()` | [09 · Safety System](../09-safety-system/README.md) |

---

## 🤖 How the ML fallback is gated (stage ②)

The rule classifier is trusted outright when it is confident. The optional local model is consulted
**only** in a narrow window — and can never escalate to fraud on weak signal.

```mermaid
flowchart TD
    R["classify_rules(signals)"] --> Q1{"rule confidence ≥ 0.6<br/>OR case_type == phishing?"}
    Q1 -- yes --> USE["✅ trust the rules"]
    Q1 -- no --> Q2{"USE_ML_FALLBACK<br/>enabled?"}
    Q2 -- no --> USE
    Q2 -- yes --> P["ml.predict(raw)"]
    P --> Q3{"prediction present<br/>AND proba ≥ threshold?"}
    Q3 -- no --> USE
    Q3 -- yes --> Q4{"ML says phishing<br/>but rules disagree?"}
    Q4 -- yes --> USE
    Q4 -- no --> ML["🤖 adopt ML label<br/>source = 'rules+ml'"]

    style USE fill:#dcfce7,stroke:#22c55e
    style ML fill:#fef9c3,stroke:#eab308
```

Implemented in `_final_classification()`. The `_ML_ELIGIBLE_FLOOR = 0.6` constant is the confidence
bar; see [Ch. 06](../06-classification/README.md) for details.

---

## 🗃️ Content-keyed LRU cache

Heavy work is cached so retried/identical tickets are served from memory — but the **echoed
`ticket_id` always reflects the current request**.

```mermaid
flowchart LR
    A["analyze(ticket)"] --> B["_content_signature(ticket)<br/>(complaint, language, channel,<br/>user_type, txns) — NO ticket_id"]
    B --> C{"in LRU cache?"}
    C -- hit --> D["reuse computed core"]
    C -- miss --> E["_investigate() → cache it"]
    D --> F["core['ticket_id'] = THIS request's id"]
    E --> F
    F --> G([AnalyzeResponse])

    style C fill:#eef7ff,stroke:#3b82f6
    style F fill:#dcfce7,stroke:#22c55e
```

- **Signature excludes `ticket_id`** → two requests with the same content but different ticket IDs
  share the cached computation, and each still echoes its own `ticket_id`.
- Cache size is `CACHE_SIZE` (default **2048**), configurable via env.
- See [Ch. 11 — Reliability & Performance](../11-reliability-and-performance/README.md).

---

## 📊 Confidence & reason codes

After the fields are decided, `investigator` assembles two metadata fields:

- **`confidence`** = `min(classification.confidence, 0.97)`, further capped at **0.65** when the
  verdict is `insufficient_data` (honest uncertainty is reflected numerically).
- **`reason_codes`** = de-duplicated union of classification + matching reasons, plus
  `safety_filtered` if the safety filter changed anything. This is the **audit trail** for why the
  service decided what it did.

---

[◀ API Contract](../03-api-contract/README.md) · [🏠 Docs Home](../README.md) · [Next ▶ Normalization](../05-normalization/README.md)
