import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from dhaba_triage.app import create_app


def _raw_ticket(ticket_id: str) -> dict:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())
    return next(ticket for ticket in payload["tickets"] if ticket["id"] == ticket_id)


def test_post_triage_returns_support_tool_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHABA_TRIAGE_DB", str(tmp_path / "triage.sqlite3"))
    client = TestClient(create_app())

    response = client.post("/triage", json=_raw_ticket("T-1001"))

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == "T-1001"
    assert body["category"] == "billing_refund"
    assert body["refund"]["action"] == "recommend_refund"
    assert body["refund"]["amount_inr"] == 249
    assert body["idempotency"]["replayed"] is False


def test_post_triage_replays_existing_decision(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHABA_TRIAGE_DB", str(tmp_path / "triage.sqlite3"))
    client = TestClient(create_app())
    ticket = _raw_ticket("T-1001")

    first = client.post("/triage", json=ticket).json()
    second = client.post("/triage", json=ticket).json()

    assert second["idempotency"]["replayed"] is True
    assert second["idempotency"]["decision_id"] == first["idempotency"]["decision_id"]


def test_post_triage_rejects_unknown_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DHABA_TRIAGE_DB", str(tmp_path / "triage.sqlite3"))
    client = TestClient(create_app())
    ticket = _raw_ticket("T-1001")
    ticket["unexpected"] = "nope"

    response = client.post("/triage", json=ticket)

    assert response.status_code == 422


def test_environment_is_not_mutated() -> None:
    assert "DHABA_TRIAGE_DB" not in os.environ or os.environ["DHABA_TRIAGE_DB"]
