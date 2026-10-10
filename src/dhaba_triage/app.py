from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request

from dhaba_triage.schemas import TicketIn, TriageResponse
from dhaba_triage.service import TriageService
from dhaba_triage.store import DecisionStore


logger = logging.getLogger("dhaba_triage")


def create_app() -> FastAPI:
    app = FastAPI(title="Dhaba Triage", version="0.1.0")
    database_path = os.getenv("DHABA_TRIAGE_DB", "triage.sqlite3")
    service = TriageService(store=DecisionStore(database_path))

    @app.middleware("http")
    async def log_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response

    @app.post("/triage", response_model=TriageResponse)
    def triage(ticket: TicketIn) -> TriageResponse:
        return service.triage(ticket)

    return app


app = create_app()
