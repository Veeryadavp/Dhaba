import json
import logging
from pathlib import Path

from dhaba_triage.logging_utils import JsonFormatter, redact
from dhaba_triage.schemas import TicketIn
from dhaba_triage.service import TriageService
from dhaba_triage.store import DecisionStore


def _ticket(ticket_id: str) -> TicketIn:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())
    raw = next(ticket for ticket in payload["tickets"] if ticket["id"] == ticket_id)
    return TicketIn.model_validate(raw)


def test_redact_masks_common_sensitive_values() -> None:
    value = {
        "body": "Email me at user@example.com. GSTIN 29ABCDE1234F1Z5. Payment pay_A2.",
        "nested": ["pay_Z9"],
    }

    redacted = redact(value)

    assert redacted == {
        "body": "Email me at [REDACTED_EMAIL]. GSTIN [REDACTED_GSTIN]. Payment [REDACTED_PAYMENT_ID].",
        "nested": ["[REDACTED_PAYMENT_ID]"],
    }


def test_json_formatter_emits_machine_readable_redacted_event() -> None:
    record = logging.LogRecord(
        name="dhaba_triage.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test_event",
        args=(),
        exc_info=None,
    )
    record.event = {"payment_id": "pay_A2", "status": "ok"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "test_event"
    assert payload["payment_id"] == "[REDACTED_PAYMENT_ID]"
    assert payload["status"] == "ok"


def test_triage_logs_safe_decision_fields_without_ticket_body(
    tmp_path: Path,
    caplog,
) -> None:
    ticket = _ticket("T-1010")
    service = TriageService(store=DecisionStore(tmp_path / "triage.sqlite3"))

    with caplog.at_level(logging.INFO, logger="dhaba_triage.service"):
        service.triage(ticket)

    events = [record.event for record in caplog.records if hasattr(record, "event")]
    assert events
    rendered = json.dumps(events)
    assert "Acme Interiors" not in rendered
    assert "29ABCDE1234F1Z5" not in rendered
    assert "pay_J1" not in rendered
    assert events[-1]["ticket_id"] == "T-1010"
    assert events[-1]["category"] == "invoice_request"
