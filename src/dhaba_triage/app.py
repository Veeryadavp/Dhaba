from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request

from dhaba_triage import __version__
from dhaba_triage.factory import build_service
from dhaba_triage.logging_utils import safe_extra
from dhaba_triage.schemas import HealthResponse, TicketIn, TriageResponse
from dhaba_triage.settings import Settings


logger = logging.getLogger("dhaba_triage")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Dhaba Triage",
        version=__version__,
        description=(
            "Support-ticket triage service with fixture classification, deterministic "
            "refund policy, idempotency, and safe logging."
        ),
    )
    service = build_service(settings)

    @app.middleware("http")
    async def log_request(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        logger.info(
            "request_completed",
            extra=safe_extra(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            ),
        )
        return response

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            classifier_mode=settings.classifier_mode,
        )

    @app.post("/triage", response_model=TriageResponse)
    def triage(ticket: TicketIn) -> TriageResponse:
        return service.triage(ticket)

    return app


app = create_app()
