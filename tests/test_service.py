import json
from pathlib import Path

from dhaba_triage.schemas import TicketIn
from dhaba_triage.service import TriageService
from dhaba_triage.store import DecisionStore


def _ticket(ticket_id: str) -> TicketIn:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())
    raw = next(ticket for ticket in payload["tickets"] if ticket["id"] == ticket_id)
    return TicketIn.model_validate(raw)


def test_triage_is_idempotent_for_same_ticket_id(tmp_path: Path) -> None:
    service = TriageService(store=DecisionStore(tmp_path / "triage.sqlite3"))
    ticket = _ticket("T-1001")

    first = service.triage(ticket)
    second = service.triage(ticket)

    assert first.idempotency.replayed is False
    assert second.idempotency.replayed is True
    assert second.idempotency.decision_id == first.idempotency.decision_id
    assert second.refund == first.refund


def test_low_confidence_for_one_word_cancel_routes_to_human(tmp_path: Path) -> None:
    service = TriageService(store=DecisionStore(tmp_path / "triage.sqlite3"))

    result = service.triage(_ticket("T-1004"))

    assert result.needs_human is True
    assert result.classifier.low_confidence is True
