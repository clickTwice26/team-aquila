"""API contract & reliability tests: status codes, schema, ticket echo, no crash."""
from __future__ import annotations

from queuestorm.schemas.response import assert_valid_enums

REQUIRED_FIELDS = [
    "ticket_id", "relevant_transaction_id", "evidence_verdict", "case_type",
    "severity", "department", "agent_summary", "recommended_next_action",
    "customer_reply", "human_review_required",
]


def test_health_exact_body(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_happy_path_schema(client, sample_cases):
    case = sample_cases[0]
    resp = client.post("/analyze-ticket", json=case["input"])
    assert resp.status_code == 200
    body = resp.json()
    for field in REQUIRED_FIELDS:
        assert field in body, f"missing field {field}"
    assert body["ticket_id"] == case["input"]["ticket_id"]
    assert_valid_enums(body)  # raises on any enum typo


def test_all_samples_return_valid_enums(client, sample_cases):
    for case in sample_cases:
        resp = client.post("/analyze-ticket", json=case["input"])
        assert resp.status_code == 200
        assert_valid_enums(resp.json())


def test_malformed_json_returns_400(client):
    resp = client.post("/analyze-ticket", content=b"{not valid json",
                       headers={"Content-Type": "application/json"})
    assert resp.status_code == 400


def test_missing_ticket_id_returns_400(client):
    resp = client.post("/analyze-ticket", json={"complaint": "hello"})
    assert resp.status_code == 400


def test_missing_complaint_returns_400(client):
    resp = client.post("/analyze-ticket", json={"ticket_id": "T1"})
    assert resp.status_code == 400
    assert resp.json().get("ticket_id") == "T1"  # echoed in error


def test_empty_complaint_returns_422(client):
    resp = client.post("/analyze-ticket", json={"ticket_id": "T2", "complaint": "   "})
    assert resp.status_code == 422
    assert resp.json().get("ticket_id") == "T2"


def test_empty_history_is_handled(client):
    resp = client.post("/analyze-ticket", json={
        "ticket_id": "T3",
        "complaint": "Someone called asking for my OTP, is this real?",
        "transaction_history": [],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["relevant_transaction_id"] is None
    assert body["case_type"] == "phishing_or_social_engineering"


def test_garbage_optional_fields_do_not_crash(client):
    resp = client.post("/analyze-ticket", json={
        "ticket_id": "T4",
        "complaint": "I paid 850 twice for my bill",
        "language": 123,                       # wrong type
        "user_type": ["weird"],                # wrong type
        "transaction_history": "not-a-list",   # wrong type
        "metadata": "nope",                    # wrong type
    })
    assert resp.status_code == 200
    assert resp.json()["ticket_id"] == "T4"


def test_ticket_id_echoed_verbatim(client):
    weird_id = "TKT-✓-9001"
    resp = client.post("/analyze-ticket", json={"ticket_id": weird_id, "complaint": "help me"})
    assert resp.status_code == 200
    assert resp.json()["ticket_id"] == weird_id


def test_relevant_transaction_id_is_null_not_string(client):
    resp = client.post("/analyze-ticket", json={
        "ticket_id": "T5", "complaint": "something is wrong with my money",
        "transaction_history": [],
    })
    assert resp.status_code == 200
    assert resp.json()["relevant_transaction_id"] is None
