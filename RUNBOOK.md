# RUNBOOK — QueueStorm Investigator

Copy-paste instructions to bring the service up. **No guessing steps.** Works even if the live URL is
down. Requires **Python 3.11+** (and optionally Docker). No secrets, no API keys, no GPU.

---

## Option A — Local (Python)

```bash
# from the repository root
python3 -m venv .venv
. .venv/bin/activate                      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .

# (optional) train the tiny local fallback classifier — the service also runs
# correctly without it (rules-only). A pre-trained ~82 KB artifact is committed.
python scripts/train_classifier.py

# run (production, multi-worker)
gunicorn -c deploy/gunicorn_conf.py queuestorm.main:app
#   or (single-worker dev):
#   uvicorn queuestorm.main:app --host 0.0.0.0 --port 8000
```

Service listens on `0.0.0.0:8000` (override with `PORT`).

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/analyze-ticket \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id":"TKT-001",
    "complaint":"I sent 5000 taka to a wrong number around 2pm today. Please help.",
    "transaction_history":[
      {"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}
    ]
  }'

# full smoke test (health + sample POSTs + 400/422 checks)
BASE_URL=http://localhost:8000 bash scripts/smoke.sh
```

---

## Option B — Docker

```bash
# from the repository root
docker build -f deploy/Dockerfile -t hackathon-team .
docker run -p 8000:8000 hackathon-team
# with env file (optional; no secrets required for this service):
#   docker run -p 8000:8000 --env-file judging.env hackathon-team
```

Or with Compose:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

The image binds `0.0.0.0:8000`, runs as a non-root user, has a built-in `HEALTHCHECK`, and contains **no
secrets**. Target size < 500 MB; no GPU, no large model weights, no runtime downloads.

---

## Configuration (all optional — safe defaults)

| Env var | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Listen port |
| `HOST` | `0.0.0.0` | Bind address |
| `WEB_CONCURRENCY` | CPU count | gunicorn worker processes |
| `USE_ML_FALLBACK` | `true` | Enable the optional local classifier |
| `ML_CONFIDENCE_THRESHOLD` | `0.45` | Min probability to accept a fallback prediction |
| `CACHE_SIZE` | `2048` | LRU cache entries |
| `MAX_BODY_BYTES` | `262144` | Reject oversized bodies (returns 400) |
| `LOG_LEVEL` | `INFO` | Log verbosity |

No third-party API keys are needed. The service runs fully offline.

---

## Tests

```bash
pip install -r requirements-dev.txt && pip install -e .
python scripts/train_classifier.py
pytest -q          # 71 tests
ruff check src tests scripts
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: queuestorm` | Run `pip install -e .` (or set `PYTHONPATH=src`). |
| `/health` not reachable from outside | Ensure the host is `0.0.0.0` and the port is published/forwarded. |
| `libgomp.so.1` missing (bare Linux) | `apt-get install -y libgomp1` (needed by scikit-learn). |
| ML fallback warning in logs | Harmless — the service runs rules-only if the model can't load. |
| Port already in use | Set a different `PORT`. |
