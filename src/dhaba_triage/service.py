from __future__ import annotations

import logging

from dhaba_triage.classifier import LOW_CONFIDENCE_THRESHOLD, FixtureClassifier
from dhaba_triage.logging_utils import safe_extra
from dhaba_triage.refunds import decide_refund
from dhaba_triage.schemas import (
    ClassifierMetadata,
    IdempotencyMetadata,
    TicketIn,
    TriageResponse,
)
from dhaba_triage.store import DecisionStore


logger = logging.getLogger("dhaba_triage.service")


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
            logger.info(
                "triage_replayed",
                extra=safe_extra(
                    ticket_id=ticket.id,
                    decision_id=existing.idempotency.decision_id,
                    category=existing.category.value,
                    refund_action=existing.refund.action,
                ),
            )
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
        saved = self.store.save(response)
        logger.info(
            "triage_completed",
            extra=safe_extra(
                ticket_id=ticket.id,
                decision_id=saved.idempotency.decision_id,
                category=saved.category.value,
                severity=saved.severity.value,
                refund_action=saved.refund.action,
                refund_amount_inr=saved.refund.amount_inr,
                needs_human=saved.needs_human,
                confidence=saved.confidence,
                classifier_mode=saved.classifier.mode,
                low_confidence=saved.classifier.low_confidence,
                prompt_injection_detected=saved.classifier.prompt_injection_detected,
                idempotency_replayed=saved.idempotency.replayed,
            ),
        )
        return saved
