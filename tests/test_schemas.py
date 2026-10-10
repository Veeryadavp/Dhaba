import json
from pathlib import Path

from dhaba_triage.schemas import TicketIn


def test_attached_tickets_validate() -> None:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())

    tickets = [TicketIn.model_validate(raw) for raw in payload["tickets"]]

    assert len(tickets) == 12
    assert tickets[0].id == "T-1001"
