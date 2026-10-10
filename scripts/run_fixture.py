from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dhaba_triage.schemas import TicketIn
from dhaba_triage.service import TriageService
from dhaba_triage.store import DecisionStore


def main() -> None:
    data_path = Path(os.getenv("DHABA_TICKETS_PATH", "data/dhaba_tickets.json"))
    payload = json.loads(data_path.read_text())

    with TemporaryDirectory() as tmpdir:
        service = TriageService(store=DecisionStore(Path(tmpdir) / "triage.sqlite3"))
        for raw_ticket in payload["tickets"]:
            ticket = TicketIn.model_validate(raw_ticket)
            result = service.triage(ticket)
            print(
                "| {ticket_id} | {category} | {severity} | {refund_action} | "
                "{amount} | {needs_human} | {confidence:.2f} | {injection} |".format(
                    ticket_id=result.ticket_id,
                    category=result.category,
                    severity=result.severity,
                    refund_action=result.refund.action,
                    amount=result.refund.amount_inr,
                    needs_human=result.needs_human,
                    confidence=result.confidence,
                    injection=result.classifier.prompt_injection_detected,
                )
            )


if __name__ == "__main__":
    main()
