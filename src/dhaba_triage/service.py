from __future__ import annotations

from dhaba_triage.classifier import LOW_CONFIDENCE_THRESHOLD, FixtureClassifier
from dhaba_triage.refunds import decide_refund
from dhaba_triage.schemas import (
    ClassifierMetadata,
    IdempotencyMetadata,
    TicketIn,
    TriageResponse,
)
from dhaba_triage.store import DecisionStore


class TriageService:
    def __init__(
        self,
        classifier: FixtureClassifier | None = None,
        store: DecisionStore | None = None,
    ) -> None:
        self.classifier = classifier or FixtureClassifier()
        self.store = store or DecisionStore()

    def triage(self, ticket: TicketIn) -> TriageResponse:
        existing = self.store.get(ticket.id)
        if existing is not None:
            return existing

        classified = self.classifier.classify(ticket)
        result = classified.result
        refund = decide_refund(ticket, result.category)
        low_confidence = result.confidence < LOW_CONFIDENCE_THRESHOLD

        response = TriageResponse(
            ticket_id=ticket.id,
            category=result.category,
            severity=result.severity,
            refund=refund,
            reply_draft=result.reply_draft,
            needs_human=result.needs_human or low_confidence or refund.action == "manual_review",
            confidence=result.confidence,
            classifier=ClassifierMetadata(
                mode=classified.mode,  # type: ignore[arg-type]
                model=classified.model,
                low_confidence=low_confidence,
                validation_recovered=classified.validation_recovered,
                prompt_injection_detected=result.prompt_injection_detected,
            ),
            idempotency=IdempotencyMetadata(
                replayed=False,
                decision_id=self.store.new_decision_id(),
            ),
        )
        return self.store.save(response)
