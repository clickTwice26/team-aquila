# QueueStorm Investigator

> **Team Aquila** — Shagato & Munia
> bKash presents **SUST CSE Carnival 2026 · Codex Community Hackathon** — Online Preliminary (AI/API SupportOps Challenge for Digital Finance)

An evidence-grounded **support copilot API** for a digital-finance platform. It reads a single customer
complaint **plus a snippet of that customer's recent transaction history**, decides **what actually
happened**, routes the case to the right team, and drafts a **safe** customer reply — one that never asks
for credentials and never promises a refund it cannot authorize.

It is a **complaint _investigator_, not a complaint classifier**: the complaint says one thing, the
transaction data may say another, and the service decides what is true. When the evidence is genuinely
unclear, it says so (`insufficient_data`) instead of guessing.

```
POST /analyze-ticket   →  structured JSON verdict (classify · investigate · route · safe reply)
GET  /health           →  {"status":"ok"}
```

---

## Highlights

- **Rules-first, deterministic engine** decides all six scored fields (`relevant_transaction_id`,
  `evidence_verdict`, `case_type`, `severity`, `department`, `human_review_required`) — reproducible,
  no LLM, no network, **~1–5 ms** per request.
- **Deterministic output safety filter** runs last on every reply: blocks credential requests, rewrites
  unauthorized refund/reversal promises, strips third-party directions and leaked secrets, and guarantees
  the credential-safety reminder in the complaint's language. Safety never depends on a model.
- **Optional tiny local fallback classifier** (scikit-learn TF-IDF + Logistic Regression, ~82 KB, CPU,
  offline) assists `case_type` **only** when the rules are not confident. Gracefully disabled if absent.
- **Multilingual** (English / Bangla / Banglish) — replies mirror the complaint's language.
- **Scalable & reliable**: stateless, async FastAPI + gunicorn multi-worker, in-process LRU cache,
  tolerant input parsing (never crashes), benchmarked at **~2,800 req/s** (p50 ≈ 11 ms, p95 ≈ 20 ms) on a
  4-worker laptop — far inside the 30 s timeout / 5 s p95 targets.
- **10/10 public sample cases** match the expected output on all six scored fields; **71 tests** pass.

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI + Starlette |
| Server | uvicorn (dev) · gunicorn + UvicornWorker (prod) |
| Validation | Pydantic v2 (strict `StrEnum` response model → impossible to emit an invalid enum) |
| Serialization | orjson |
| Optional ML | scikit-learn + joblib (tiny local fallback classifier) |
| Tests / tooling | pytest · ruff · mypy · GitHub Actions CI |

---

## Project structure

```
src/queuestorm/            # installable package (src layout)
├── main.py                # app factory + ASGI entrypoint (queuestorm.main:app)
├── api/                   # HTTP layer
│   ├── routes/            #   health.py, analyze.py
│   ├── errors.py          #   controlled, non-sensitive error responses
│   └── middleware.py      #   timing + access logging
├── core/                  # config (env) + logging
├── schemas/               # enums (source of truth) + request/response models
├── domain/                # business logic (pure, unit-tested)
│   ├── normalization.py   #   amounts, language, counterparty hints (EN/BN/Banglish)
│   ├── classification.py  #   case_type rules + tie-break order
│   ├── matching.py        #   relevant_transaction_id + evidence_verdict
│   ├── routing.py         #   department + severity + human_review
│   ├── templates.py       #   multilingual, safe-by-construction replies
│   ├── safety.py          #   deterministic OUTPUT SAFETY FILTER
│   ├── parsing.py         #   tolerant request → domain model
│   └── investigator.py    #   pipeline orchestrator + LRU cache
└── ml/                    # optional fallback classifier + artifacts/
deploy/                    # Dockerfile, docker-compose.yml, gunicorn_conf.py
scripts/                   # train_classifier.py, generate_sample_output.py, smoke.sh
tests/                     # unit/ + integration/
contexts/                  # hackathon reference docs (not part of the app)
```

---

## Quick start

```bash
# 1) Install (Python 3.11+)
python -m pip install -r requirements.txt
python -m pip install -e .

# 2) (optional) train the tiny local fallback classifier — the service also
#    runs fine without it (rules-only).
python scripts/train_classifier.py

# 3) Run
uvicorn queuestorm.main:app --host 0.0.0.0 --port 8000        # dev
gunicorn -c deploy/gunicorn_conf.py queuestorm.main:app       # prod (multi-worker)

# 4) Verify
curl http://localhost:8000/health
BASE_URL=http://localhost:8000 bash scripts/smoke.sh
```

`make help` lists all developer tasks (`install`, `dev`, `train`, `run`, `run-prod`, `test`, `lint`,
`sample`, `smoke`, `docker-build`, `docker-run`).

### Docker

```bash
docker build -f deploy/Dockerfile -t queuestorm-investigator:latest .
docker run -p 8000:8000 queuestorm-investigator:latest
# or: docker compose -f deploy/docker-compose.yml up --build
```

---

## API

### `POST /analyze-ticket`

Request (only `ticket_id` and `complaint` are required):

```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please help.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "transaction_history": [
    {"transaction_id": "TXN-9101", "timestamp": "2026-04-14T14:08:22Z", "type": "transfer", "amount": 5000, "counterparty": "+8801719876543", "status": "completed"}
  ]
}
```

Response:

```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to the wrong recipient and seeks help recovering it.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Our dispute resolution team will review the case and contact you through official support channels. Please do not share your PIN or OTP with anyone.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["keyword:wrong_transfer", "amount_match", "type_match", "transaction_match"]
}
```

**Status codes:** `200` success · `400` malformed JSON / missing `ticket_id`|`complaint` · `422` empty
complaint · `500` internal error (non-sensitive body, `ticket_id` echoed). The service **never crashes**
on malformed input. See [sample_output.json](sample_output.json) for all 10 public cases.

---

## AI approach & reasoning logic

The service is a **deterministic state machine**, computed in this order:

1. **Normalize** — extract amounts (ignoring phone numbers/times, handling Bangla digits & commas),
   detect language, surface counterparty hints and status cues.
2. **Classify `case_type`** from the complaint via prioritized keyword rules (EN + Bangla), with a
   **safety-first tie-break** (`phishing` > `duplicate_payment` > `wrong_transfer` > …). If the rules are
   low-confidence, the **optional local ML fallback** may assist — but it can never flip a confident
   phishing/safety label.
3. **Match `relevant_transaction_id`** by amount (strongest), type, status and counterparty signals.
   When several transactions plausibly match and nothing disambiguates → **`null`** (don't guess). For
   duplicates, the **second/later** transaction is selected.
4. **Judge `evidence_verdict`** — `consistent` (data corroborates), `inconsistent` (data contradicts, e.g.
   an established-recipient pattern behind a "wrong transfer" claim), or `insufficient_data`.
5. **Route `department`**, **set `severity`**, **set `human_review_required`** — pure functions of the
   decided fields (`user_type` confirms merchant/agent routes).
6. **Draft text** (mirroring complaint language) → **enforce safety** as the final, independent gate.

---

## Safety logic

Fintech safety is a hard requirement; violations carry direct score penalties. The
[safety filter](src/queuestorm/domain/safety.py) runs on **every** `customer_reply` and
`recommended_next_action` before they leave the service:

| Rule | Guarantee |
|---|---|
| **No credential requests** (PIN/OTP/password/card/CVV) | Any request pattern is removed; the service only ever *warns against sharing*. |
| **No unauthorized financial confirmation** | "we will refund/reverse/unlock…" is rewritten to *"any eligible amount will be returned through official channels."* Checked on **both** the reply and the next-action. |
| **No third-party direction** | Copied phone numbers / URLs / "call this number" are replaced with *official support channels*. |
| **Prompt-injection resistant** | The complaint is treated as untrusted **data**, never instructions; embedded commands and leaked secrets are stripped. |
| **Credential reminder** | Appended in the complaint's language (English or Bangla) unless already present. |

Because every scored decision and the safety filter are deterministic, an LLM outage, quota limit, or
jailbreak attempt **cannot** affect correctness or safety.

## MODELS

The QueueStorm Investigator is **rules-first**. All scored decisions (transaction matching,
`evidence_verdict`, `case_type`, `severity`, `department`, `human_review_required`) and **every safety
guardrail** are made by a deterministic rule engine — no model is required for correctness.

| Model | Role | Where it runs | Why chosen | Fallback |
|-------|------|---------------|------------|----------|
| **Deterministic rule engine** (in-house, Python) | Source of truth: tx match, evidence verdict, classification, routing, severity, escalation, **safety filter** | In-process (no GPU, no weights, no network) | Fast (~1–5 ms), reproducible, zero quota/cost/injection risk | N/A — always available |
| **Local fallback classifier** (scikit-learn TF-IDF + Logistic Regression, ~82 KB) | OPTIONAL: assists `case_type` only when rule confidence is low | In-process, CPU, offline | Tiny, deterministic, sub-ms; robustness hedge for unusual phrasings | Rules-only (auto-disabled if scikit-learn/artifact absent) |
| **Cloud LLM** | **Not used** in the judged path | — | Adds latency, quota, availability and safety risk for **zero** gain on the auto-scored fields | — |

**Cost & availability:** **$0** — no third-party API keys, no metered calls, no model downloads at
runtime. The fallback model is trained offline (`scripts/train_classifier.py`) and ships as ~82 KB of
package data. Runs comfortably within 2 vCPU / 4 GB.

---

## Performance & scalability

- **Stateless** → scales horizontally; run N gunicorn workers (`WEB_CONCURRENCY`, defaults to CPU count).
- **In-process LRU cache** keyed on request *content* (not `ticket_id`) serves retried/identical tickets
  from memory; the echoed `ticket_id` always reflects the current request.
- **`/health` is static and dependency-free** → ready well within the 60 s window even on a cold start;
  the optional model loads lazily and never blocks readiness.
- Benchmark (4 workers, laptop): **~2,800 req/s**, p50 ≈ 11 ms, p95 ≈ 20 ms.

---

## Testing

```bash
python -m pytest          # 71 tests: 10 sample cases, safety red-team, API contract, unit logic
ruff check src tests scripts
```

---

## Assumptions & known limitations

- **Synthetic data only** — no real customer data, no live payment integration, no production-scale deploy.
- `case_type` rules are keyword-driven; very unusual phrasings rely on the tiny fallback classifier, which
  is trained on a small synthetic set and is intentionally conservative (it never escalates to fraud on
  weak signal).
- The **high-value severity escalator** (≥ 100,000 BDT) is a non-authoritative heuristic deliberately set
  well above the public sample range (largest sample = 15,000 BDT) so it never alters a sample.
- Time cues ("around 2pm", "yesterday") are used only as soft ranking signals — no timezone arithmetic.
- The reference sample file is provided as `SUST_Preli_Sample_Cases.json` (the problem statement also
  refers to it as `QueueStorm_Preli_Sample_Cases.json`).

---

## License

MIT
