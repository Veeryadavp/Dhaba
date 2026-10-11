import json
import subprocess
import sys


def test_fixture_replay_markdown_output_has_header_and_all_tickets() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_fixture.py", "--format", "markdown"],
        check=True,
        capture_output=True,
        text=True,
    )

    lines = result.stdout.strip().splitlines()
    assert lines[0].startswith("| Ticket | Category | Severity |")
    assert len([line for line in lines if line.startswith("| T-")]) == 12
    assert "| T-1003 | account_access | high | none | 0 | true | 0.60 | true |" in lines


def test_fixture_replay_jsonl_output_has_machine_readable_responses() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_fixture.py", "--format", "jsonl"],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = [json.loads(line) for line in result.stdout.strip().splitlines()]

    assert len(rows) == 12
    assert rows[0]["ticket_id"] == "T-1001"
    assert rows[0]["refund"]["action"] == "recommend_refund"
    assert rows[2]["classifier"]["prompt_injection_detected"] is True
