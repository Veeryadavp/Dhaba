from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from dhaba_triage.schemas import (
    Category,
    Purchase,
    PurchaseStatus,
    PurchaseType,
    RefundDecision,
    RefundReasonCode,
    TicketIn,
)


REFUND_WINDOW = timedelta(days=7)


def decide_refund(ticket: TicketIn, category: Category) -> RefundDecision:
    text = f"{ticket.subject}\n{ticket.body}".lower()
    successful = [purchase for purchase in ticket.purchases if purchase.status == PurchaseStatus.SUCCESSFUL]
    successful_renewals = [purchase for purchase in successful if purchase.type == PurchaseType.RENEWAL]
    latest_renewal = max(successful_renewals, key=lambda purchase: purchase.at, default=None)

    if category == Category.FRAUD_OR_UNAUTHORIZED:
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=RefundReasonCode.FRAUD_CLAIM_MANUAL_REVIEW,
            explanation="Fraud or unauthorized-use claims require identity and payment review.",
            action="manual_review",
        )

    duplicate = _duplicate_successful_charge(successful_renewals)
    if duplicate is not None:
        return RefundDecision(
            eligible=True,
            amount_inr=duplicate.amount_inr,
            purchase_ids=[duplicate.id],
            reason_code=RefundReasonCode.DUPLICATE_SUCCESSFUL_CHARGE,
            explanation="A second successful renewal for the same amount appears on the same day.",
            action="recommend_refund",
        )

    if "double charge" in text and _has_failed_or_initiated_renewal(ticket.purchases):
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=RefundReasonCode.FAILED_OR_INITIATED_PAYMENT_NO_REFUND,
            explanation="Only one successful renewal is present; the other same-day attempt did not capture.",
            action="none",
        )

    if category not in {Category.BILLING_REFUND, Category.GENERAL_COMPLAINT}:
        if not successful:
            return RefundDecision(
                eligible=False,
                amount_inr=0,
                purchase_ids=[],
                reason_code=RefundReasonCode.NO_SUCCESSFUL_PAYMENT,
                explanation="No successful payment is available to refund.",
                action="none",
            )
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=RefundReasonCode.NOT_REFUND_RELATED,
            explanation="The ticket is not primarily a refund request.",
            action="none",
        )

    if latest_renewal is None:
        pending = [purchase for purchase in ticket.purchases if purchase.status != PurchaseStatus.SUCCESSFUL]
        reason = (
            RefundReasonCode.FAILED_OR_INITIATED_PAYMENT_NO_REFUND
            if pending
            else RefundReasonCode.NO_SUCCESSFUL_PAYMENT
        )
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=reason,
            explanation="There is no successful renewal charge available to refund.",
            action="none",
        )

    if ticket.app_opens_since_renewal > 3:
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=RefundReasonCode.NO_REFUND_DUE_USAGE,
            explanation="The latest renewal has meaningful post-renewal usage.",
            action="none",
        )

    age = ticket.received_at - latest_renewal.at
    if age < timedelta(0):
        return RefundDecision(
            eligible=False,
            amount_inr=0,
            purchase_ids=[],
            reason_code=RefundReasonCode.AMBIGUOUS_MANUAL_REVIEW,
            explanation="The renewal timestamp is after the ticket timestamp and needs review.",
            action="manual_review",
        )

    if latest_renewal.amount_inr == 1499 and ticket.app_opens_since_renewal == 0:
        return RefundDecision(
            eligible=True,
            amount_inr=latest_renewal.amount_inr,
            purchase_ids=[latest_renewal.id],
            reason_code=RefundReasonCode.ANNUAL_RENEWAL_NO_USAGE,
            explanation="Annual renewal has no post-renewal usage.",
            action="recommend_refund",
        )

    if age <= REFUND_WINDOW and ticket.app_opens_since_renewal <= 3:
        return RefundDecision(
            eligible=True,
            amount_inr=latest_renewal.amount_inr,
            purchase_ids=[latest_renewal.id],
            reason_code=RefundReasonCode.TRIAL_CONVERSION_NO_USAGE,
            explanation="Recent renewal after trial has little or no post-renewal usage.",
            action="recommend_refund",
        )

    return RefundDecision(
        eligible=False,
        amount_inr=0,
        purchase_ids=[],
        reason_code=RefundReasonCode.AMBIGUOUS_MANUAL_REVIEW,
        explanation="Refund eligibility is ambiguous under the documented local policy.",
        action="manual_review",
    )


def _duplicate_successful_charge(purchases: list[Purchase]) -> Purchase | None:
    by_day_and_amount: dict[tuple[str, int], list[Purchase]] = defaultdict(list)
    for purchase in purchases:
        day = purchase.at.date().isoformat()
        by_day_and_amount[(day, purchase.amount_inr)].append(purchase)

    for matches in by_day_and_amount.values():
        if len(matches) > 1:
            return sorted(matches, key=lambda purchase: purchase.at)[-1]
    return None


def _has_failed_or_initiated_renewal(purchases: list[Purchase]) -> bool:
    return any(
        purchase.type == PurchaseType.RENEWAL and purchase.status != PurchaseStatus.SUCCESSFUL
        for purchase in purchases
    )
