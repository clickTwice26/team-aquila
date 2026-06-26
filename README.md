<div align="center">

# 🛰️ QueueStorm Investigator

**An evidence-grounded support-copilot API for digital finance.**

Reads one customer complaint **plus a snippet of recent transaction history**, decides **what actually
happened**, routes the case to the right team, and drafts a **safe** customer reply.

<br/>

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)
![Samples](https://img.shields.io/badge/public%20samples-10%2F10-brightgreen)
![Cost](https://img.shields.io/badge/judged%20path-no%20LLM%20%C2%B7%20%240-7C3AED)
![License](https://img.shields.io/badge/license-MIT-blue)

<sub>Team Aquila — Shagato & Munia · bKash presents **SUST CSE Carnival 2026 · Codex Community Hackathon**<br/>
Online Preliminary — AI/API SupportOps Challenge for Digital Finance</sub>

</div>

---

It is a **complaint _investigator_, not a complaint classifier**: the complaint says one thing, the
transaction data may say another, and the service decides what is true. When the evidence is genuinely
unclear, it says so (`insufficient_data`) instead of guessing.

```text
POST /analyze-ticket   →  structured JSON verdict  (classify · investigate · route · safe reply)
GET  /health           →  {"status": "ok"}
```

---

## Table of Contents

- [Overview](#overview)
- [Highlights](#highlights)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Performance and Reliability](#performance-and-reliability)
- [Testing](#testing)
- [Assumptions and Limitations](#assumptions-and-limitations)
- [License](#license)

---

## Overview

Fintech support teams drown in tickets, and every ticket hides a question of fact. A customer writes
*"I sent 5000 taka to the wrong number, please reverse it!"* — but is it really a wrong transfer? Maybe
they have sent money to that exact number three times before. Maybe the transaction never happened. Maybe
it is a scammer fishing for an OTP.

QueueStorm Investigator automates that judgement into **one API call**. It cross-checks the complaint
against the transaction history, classifies and routes the case, and writes a reply that **never asks for
credentials and never promises a refund it cannot authorize** — or honestly returns `insufficient_data`
when the evidence does not support a confident answer.

> **Design philosophy:** *"A simple, reliable, safe API will score higher than a complex but unreliable
> one."* Every scored decision is made by deterministic code; the optional model is polish, never the
> source of truth.

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
- **Scalable and reliable** — stateless, async FastAPI + gunicorn multi-worker, in-process LRU cache,
  tolerant input parsing (never crashes); benchmarked at **~2,800 req/s** (p50 ≈ 11 ms, p95 ≈ 20 ms) on a
  4-worker laptop, far inside the 30 s timeout / 5 s p95 targets.
- **Validated** — 10/10 public sample cases match the expected output on all six scored fields; **92
  automated tests** pass.

---

## Documentation

Full architecture documentation — **14 chapters with 40+ Mermaid diagrams** (use-case, component,
sequence, activity) — lives in **[`docs/`](docs/README.md)**. Start there for the complete walkthrough;
every chapter traces its claims to the code and is verified against it.

| Chapter | Topic |
|---|---|
| [01 · Overview & Mission](docs/01-overview/README.md) | The problem, the "investigator twist", actors, scoring map |
| [02 · System Architecture](docs/02-architecture/README.md) | Layers, components, data flow, dependency rule, tech stack |
| [03 · API Contract](docs/03-api-contract/README.md) | Endpoints, request/response schema, enums, status codes |
| [04 · Investigation Pipeline](docs/04-investigation-pipeline/README.md) | The 8-stage orchestrator, ML gating, content cache |
| [05 · Normalization & Signals](docs/05-normalization/README.md) | Amounts, language, counterparty, status cues (EN/BN/Banglish) |
| [06 · Case-Type Classification](docs/06-classification/README.md) | Keyword rules, tie-break order, optional ML fallback |
| [07 · Evidence Matching & Verdict](docs/07-evidence-matching/README.md) | `relevant_transaction_id` + `evidence_verdict` (the investigator's brain) |
| [08 · Routing, Severity & Review](docs/08-routing-and-severity/README.md) | `department`, `severity`, `human_review_required` |
| [09 · Safety System](docs/09-safety-system/README.md) | The output safety filter, P1/P2/P3, injection defense |
| [10 · Text Generation](docs/10-text-generation/README.md) | Safe-by-construction multilingual replies |
| [11 · Reliability & Performance](docs/11-reliability-and-performance/README.md) | Never-crash handling, caching, latency budget |
| [12 · Deployment](docs/12-deployment/README.md) | Docker, gunicorn, hosting, cold-start, runbook |
| [13 · Testing & Validation](docs/13-testing-and-validation/README.md) | 92 tests, safety red-team, classifier scoring |
| [14 · Decision Matrix](docs/14-decision-matrix/README.md) | All 10 sample cases, field-by-field |

**Also in [`docs/`](docs/README.md):** [`diagrams/`](docs/diagrams/README.md) (headline system diagrams) ·
[`SLIDES.md`](docs/SLIDES.md) (4-slide presentation deck) ·
[`VIDEO-SCRIPT.md`](docs/VIDEO-SCRIPT.md) (90-second architecture-video storyboard).

---

## Architecture

A **rules-first hybrid**: a thin async HTTP shell wraps a pure, deterministic domain core. Web concerns
live at the edge; business logic (`domain/`) has **zero web and zero ML dependencies**, so it is fast,
reproducible, and independently unit-testable. → Full detail in [Chapter 02](docs/02-architecture/README.md).

### Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI + Starlette |
| Server | uvicorn (dev) · gunicorn + UvicornWorker (prod) |
| Validation | Pydantic v2 (strict `StrEnum` response model → impossible to emit an invalid enum) |
| Serialization | orjson |
| Optional ML | scikit-learn + joblib (tiny local fallback classifier) |
| Tests / tooling | pytest · ruff · mypy · GitHub Actions CI |

### Project structure

```text
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
scripts/                   # train_classifier.py, generate_sample_output.py, score_cases.py, smoke.sh
tests/                     # unit/ + integration/ (92 tests) + cases.json multilingual corpus
docs/                      # full architecture documentation — 14 chapters + diagrams + slides + video script
contexts/                  # hackathon reference docs (not part of the app)
```

---

## Quick Start

### Local (Python 3.11+)

```bash
# 1) Install
python -m pip install -r requirements.txt
python -m pip install -e .

# 2) (optional) train the tiny local fallback classifier — the service also
#    runs fine without it (rules-only).
python scripts/train_classifier.py

# 3) Run
uvicorn queuestorm.main:app --host 0.0.0.0 --port 8000        # dev (single worker)
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

The image is `python:3.11-slim`, runs as a non-root user, binds `0.0.0.0:8000`, trains the ~82 KB model
at build time, ships **no secrets**, and performs **no runtime downloads**. See
[`RUNBOOK.md`](RUNBOOK.md) and [Chapter 12](docs/12-deployment/README.md).

---

## API Reference

The judge harness exercises exactly two endpoints.

### `GET /health`

Static, dependency-free — ready well within the 60 s window even on a cold start.

```http
GET /health  →  200  {"status": "ok"}
```

### `POST /analyze-ticket`

Only `ticket_id` and `complaint` are required; everything else is optional and tolerated.

**Request**

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

**Response**

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

### Status codes

| Code | Meaning |
|---|---|
| `200` | Successful analysis; body conforms to the response schema |
| `400` | Malformed JSON, or missing `ticket_id` / `complaint` |
| `422` | Schema-valid but empty/whitespace-only `complaint` |
| `500` | Internal error — non-sensitive body, `ticket_id` echoed, never a stack trace |

The service **never crashes** on malformed input. See [`sample_output.json`](sample_output.json) for the
responses to all 10 public cases, and [Chapter 03](docs/03-api-contract/README.md) for the full contract.

---

## How It Works

### Reasoning pipeline (AI approach)

The service is a **deterministic state machine**, computed in this exact order
([Chapter 04](docs/04-investigation-pipeline/README.md)):

1. **Normalize** — extract amounts (ignoring phone numbers/times, handling Bangla digits and commas),
   detect language, surface counterparty hints and status cues.
2. **Classify `case_type`** from the complaint via prioritized keyword rules (EN + Bangla), with a
   **safety-first tie-break** (`phishing` > `duplicate_payment` > `wrong_transfer` > …). If the rules are
   low-confidence, the **optional local ML fallback** may assist — but it can never flip a confident
   phishing/safety label.
3. **Match `relevant_transaction_id`** by amount (strongest), type, status, and counterparty signals.
   When several transactions plausibly match and nothing disambiguates → **`null`** (don't guess). For
   duplicates, the **second/later** transaction is selected.
4. **Judge `evidence_verdict`** — `consistent` (data corroborates), `inconsistent` (data contradicts,
   e.g. an established-recipient pattern behind a "wrong transfer" claim), or `insufficient_data`.
5. **Route `department`**, **set `severity`**, **set `human_review_required`** — pure functions of the
   decided fields (`user_type` confirms merchant/agent routes).
6. **Draft text** (mirroring complaint language) → **enforce safety** as the final, independent gate.

### Models

The QueueStorm Investigator is **rules-first**. All scored decisions and **every safety guardrail** are
made by a deterministic rule engine — no model is required for correctness.

| Model | Role | Where it runs | Fallback |
|---|---|---|---|
| **Deterministic rule engine** (in-house, Python) | Source of truth: tx match, evidence verdict, classification, routing, severity, escalation, **safety filter** | In-process (no GPU, no weights, no network) | N/A — always available |
| **Local fallback classifier** (scikit-learn TF-IDF + Logistic Regression, ~82 KB) | OPTIONAL: assists `case_type` only when rule confidence is low | In-process, CPU, offline | Rules-only (auto-disabled if scikit-learn / artifact absent) |
| **Cloud LLM** | **Not used** in the judged path | — | — |

**Cost and availability:** **$0** — no third-party API keys, no metered calls, no model downloads at
runtime. The fallback model is trained offline (`scripts/train_classifier.py`) and ships as ~82 KB of
package data. Runs comfortably within 2 vCPU / 4 GB. Because every scored decision and the safety filter
are deterministic, an LLM outage, quota limit, or jailbreak attempt **cannot** affect correctness or
safety.

### Safety logic

The [safety filter](src/queuestorm/domain/safety.py) runs on **every** `customer_reply` and
`recommended_next_action` before they leave the service ([Chapter 09](docs/09-safety-system/README.md)):

| Rule | Guarantee |
|---|---|
| **No credential requests** (PIN/OTP/password/card/CVV) | Any request pattern is removed; the service only ever *warns against sharing*. |
| **No unauthorized financial confirmation** | "we will refund/reverse/unlock…" is rewritten to *"any eligible amount will be returned through official channels."* Checked on **both** the reply and the next-action. |
| **No third-party direction** | Copied phone numbers / URLs / "call this number" are replaced with *official support channels*. |
| **Prompt-injection resistant** | The complaint is treated as untrusted **data**, never instructions; embedded commands and leaked secrets are stripped. |
| **Credential reminder** | Appended in the complaint's language (English or Bangla) unless already present. |

---

## Performance and Reliability

- **Stateless** → scales horizontally; run N gunicorn workers (`WEB_CONCURRENCY`, defaults to CPU count).
- **In-process LRU cache** keyed on request *content* (not `ticket_id`) serves retried/identical tickets
  from memory; the echoed `ticket_id` always reflects the current request.
- **`/health` is static and dependency-free** → ready well within the 60 s window even on a cold start;
  the optional model loads lazily and never blocks readiness.
- **Never-crash handling** — tolerant parsing plus a top-level guard turn any unexpected error into a
  controlled response; the process never exits.
- **Benchmark** (4 workers, laptop): **~2,800 req/s**, p50 ≈ 11 ms, p95 ≈ 20 ms.

→ See [Chapter 11](docs/11-reliability-and-performance/README.md).

---

## Testing

```bash
python -m pytest          # 92 tests: 10 sample cases, safety red-team, API contract, multilingual corpus, unit logic
ruff check src tests scripts
```

Test suites cover normalization, classification, matching/routing, the safety red-team, the API contract,
sample functional-equivalence, and a 292-case multilingual corpus. CI
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs ruff + pytest on Python 3.11/3.12 on every
push. → See [Chapter 13](docs/13-testing-and-validation/README.md).

---

## Assumptions and Limitations

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

Released under the [MIT License](LICENSE).

<div align="center"><sub>Built by <b>Team Aquila</b> — Shagato & Munia · SUST CSE Carnival 2026</sub></div>
