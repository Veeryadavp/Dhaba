import json
from pathlib import Path

from dhaba_triage.classifier import FixtureClassifier
from dhaba_triage.refunds import decide_refund
from dhaba_triage.schemas import Category, RefundReasonCode, TicketIn


def _ticket(ticket_id: str) -> TicketIn:
    payload = json.loads(Path("data/dhaba_tickets.json").read_text())
    raw = next(ticket for ticket in payload["tickets"] if ticket["id"] == ticket_id)
    return TicketIn.model_validate(raw)


def test_recent_trial_conversion_with_low_usage_is_refundable() -> None:
    ticket = _ticket("T-1001")

    decision = decide_refund(ticket, Category.BILLING_REFUND)

    assert decision.action == "recommend_refund"
    assert decision.amount_inr == 249
    assert decision.purchase_ids == ["pay_A2"]
    assert decision.reason_code == RefundReasonCode.TRIAL_CONVERSION_NO_USAGE


def test_fraud_claim_requires_human_review_not_auto_refund() -> None:
    ticket = _ticket("T-1008")

    decision = decide_refund(ticket, Category.FRAUD_OR_UNAUTHORIZED)

    assert decision.action == "manual_review"
    assert decision.eligible is False


def test_initiated_payment_is_not_refunded() -> None:
    ticket = _ticket("T-1005")

    decision = decide_refund(ticket, Category.BILLING_ACTIVATION_ISSUE)

    assert decision.action == "none"
    assert decision.amount_inr == 0


def test_failed_attempt_does_not_become_double_charge_refund() -> None:
    ticket = _ticket("T-1009")

    decision = decide_refund(ticket, Category.BILLING_REFUND)

    assert decision.action == "none"
    assert decision.reason_code == RefundReasonCode.FAILED_OR_INITIATED_PAYMENT_NO_REFUND


def test_prompt_injection_is_detected_by_classifier() -> None:
    ticket = _ticket("T-1003")

    result = FixtureClassifier().classify(ticket).result

    assert result.prompt_injection_detected is True
    assert result.needs_human is True
