#!/usr/bin/env bash
# Smoke-test a running deployment from OUTSIDE the host.
#   BASE_URL=https://your-service.example.com bash scripts/smoke.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
echo "Smoke testing ${BASE_URL}"

echo "== GET /health =="
curl -fsS "${BASE_URL}/health"; echo

echo "== POST /analyze-ticket (wrong transfer) =="
curl -fsS -X POST "${BASE_URL}/analyze-ticket" \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "SMOKE-001",
    "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please help.",
    "language": "en",
    "channel": "in_app_chat",
    "user_type": "customer",
    "transaction_history": [
      {"transaction_id": "TXN-9101", "timestamp": "2026-04-14T14:08:22Z", "type": "transfer", "amount": 5000, "counterparty": "+8801719876543", "status": "completed"}
    ]
  }'; echo

echo "== POST /analyze-ticket (phishing, empty history) =="
curl -fsS -X POST "${BASE_URL}/analyze-ticket" \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"SMOKE-002","complaint":"Someone called asking for my OTP, is this real?","transaction_history":[]}'; echo

echo "== POST /analyze-ticket (malformed JSON -> 400) =="
curl -s -o /dev/null -w "status=%{http_code}\n" -X POST "${BASE_URL}/analyze-ticket" \
  -H 'Content-Type: application/json' -d '{not json'

echo "== POST /analyze-ticket (empty complaint -> 422) =="
curl -s -o /dev/null -w "status=%{http_code}\n" -X POST "${BASE_URL}/analyze-ticket" \
  -H 'Content-Type: application/json' -d '{"ticket_id":"SMOKE-003","complaint":"   "}'

echo "All smoke checks issued."
