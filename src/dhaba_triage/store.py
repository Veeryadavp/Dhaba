from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from dhaba_triage.schemas import TriageResponse


class DecisionStore:
    def __init__(self, path: str | Path = "triage.sqlite3") -> None:
        self.path = Path(path)
        self._ensure_schema()

    def get(self, ticket_id: str) -> TriageResponse | None:
        with self._connect() as conn:
            row = conn.execute(
                "select response_json from triage_decisions where ticket_id = ?",
                (ticket_id,),
            ).fetchone()
        if row is None:
            return None

        data = json.loads(row["response_json"])
        data["idempotency"]["replayed"] = True
        return TriageResponse.model_validate(data)

    def save(self, response: TriageResponse) -> TriageResponse:
        payload = response.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                insert into triage_decisions(ticket_id, decision_id, response_json)
                values (?, ?, ?)
                """,
                (
                    response.ticket_id,
                    response.idempotency.decision_id,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        return response

    def new_decision_id(self) -> str:
        return f"dec_{uuid.uuid4().hex}"

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists triage_decisions (
                    ticket_id text primary key,
                    decision_id text not null unique,
                    response_json text not null,
                    created_at text not null default current_timestamp
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
