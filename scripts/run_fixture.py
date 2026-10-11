from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from dhaba_triage.schemas import TicketIn
from dhaba_triage.service import TriageService
from dhaba_triage.store import DecisionStore


OutputFormat = Literal["markdown", "jsonl"]


def load_results(data_path: Path) -> list[dict]:
    payload = json.loads(data_path.read_text())
    rows: list[dict] = []

    with TemporaryDirectory() as tmpdir:
        service = TriageService(store=DecisionStore(Path(tmpdir) / "triage.sqlite3"))
        for raw_ticket in payload["tickets"]:
            ticket = TicketIn.model_validate(raw_ticket)
            result = service.triage(ticket)
            rows.append(result.model_dump(mode="json"))
    return rows


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "| Ticket | Category | Severity | Refund action | Amount | Human? | Confidence | Injection? |",
        "| --- | --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {ticket_id} | {category} | {severity} | {refund_action} | "
            "{amount} | {needs_human} | {confidence:.2f} | {injection} |".format(
                ticket_id=row["ticket_id"],
                category=row["category"],
                severity=row["severity"],
                refund_action=row["refund"]["action"],
                amount=row["refund"]["amount_inr"],
                needs_human=str(row["needs_human"]).lower(),
                confidence=row["confidence"],
                injection=str(row["classifier"]["prompt_injection_detected"]).lower(),
            )
        )
    return "\n".join(lines)


def render_jsonl(rows: list[dict]) -> str:
    return "\n".join(json.dumps(row, sort_keys=True) for row in rows)


def render(rows: list[dict], output_format: OutputFormat) -> str:
    if output_format == "markdown":
        return render_markdown(rows)
    if output_format == "jsonl":
        return render_jsonl(rows)
    raise ValueError(f"Unsupported output format: {output_format}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Dhaba tickets through fixture triage.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(os.getenv("DHABA_TICKETS_PATH", "data/dhaba_tickets.json")),
        help="Path to a dhaba_tickets.json-shaped file.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "jsonl"],
        default="markdown",
        help="Output format.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_results(args.input)
    print(render(rows, args.format))


if __name__ == "__main__":
    main()
