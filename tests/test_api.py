import json
from pathlib import Path

from fastapi.testclient import TestClient

from dhaba_triage.app import create_app
from dhaba_triage.settings import Settings


def _raw_ticket(ticket_id: str) -> dict:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())
    return next(ticket for ticket in payload["tickets"] if ticket["id"] == ticket_id)


def test_post_triage_returns_support_tool_response(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(database_path=str(tmp_path / "triage.sqlite3")))
    )

    response = client.post("/triage", json=_raw_ticket("T-1001"))

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == "T-1001"
    assert body["category"] == "billing_refund"
    assert body["refund"]["action"] == "recommend_refund"
    assert body["refund"]["amount_inr"] == 249
    assert body["idempotency"]["replayed"] is False


def test_post_triage_replays_existing_decision(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(database_path=str(tmp_path / "triage.sqlite3")))
    )
    ticket = _raw_ticket("T-1001")

    first = client.post("/triage", json=ticket).json()
    second = client.post("/triage", json=ticket).json()

    assert second["idempotency"]["replayed"] is True
    assert second["idempotency"]["decision_id"] == first["idempotency"]["decision_id"]


def test_post_triage_rejects_unknown_fields(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(database_path=str(tmp_path / "triage.sqlite3")))
    )
    ticket = _raw_ticket("T-1001")
    ticket["unexpected"] = "nope"

    response = client.post("/triage", json=ticket)

    assert response.status_code == 422
