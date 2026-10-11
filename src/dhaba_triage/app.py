from __future__ import annotations

import logging

from fastapi import FastAPI, Request

from dhaba_triage.factory import build_service
from dhaba_triage.schemas import TicketIn, TriageResponse
from dhaba_triage.settings import Settings


logger = logging.getLogger("dhaba_triage")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="Dhaba Triage", version="0.1.0")
    service = build_service(settings)

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
