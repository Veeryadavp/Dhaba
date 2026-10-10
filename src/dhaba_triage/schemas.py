from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PurchaseType(StrEnum):
    TRIAL = "trial"
    RENEWAL = "renewal"


class PurchaseStatus(StrEnum):
    INITIATED = "initiated"
    FAILED = "failed"
    SUCCESSFUL = "successful"


class Category(StrEnum):
    BILLING_REFUND = "billing_refund"
    BILLING_ACTIVATION_ISSUE = "billing_activation_issue"
    TECHNICAL_ISSUE = "technical_issue"
    ACCOUNT_ACCESS = "account_access"
    CANCELLATION = "cancellation"
    FEATURE_REQUEST = "feature_request"
    INVOICE_REQUEST = "invoice_request"
    PRE_SALES_QUESTION = "pre_sales_question"
    FRAUD_OR_UNAUTHORIZED = "fraud_or_unauthorized"
    GENERAL_COMPLAINT = "general_complaint"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RefundReasonCode(StrEnum):
    TRIAL_CONVERSION_NO_USAGE = "trial_conversion_no_usage"
    ANNUAL_RENEWAL_NO_USAGE = "annual_renewal_no_usage"
    DUPLICATE_SUCCESSFUL_CHARGE = "duplicate_successful_charge"
    FAILED_OR_INITIATED_PAYMENT_NO_REFUND = "failed_or_initiated_payment_no_refund"
    FRAUD_CLAIM_MANUAL_REVIEW = "fraud_claim_manual_review"
    NOT_REFUND_RELATED = "not_refund_related"
    AMBIGUOUS_MANUAL_REVIEW = "ambiguous_manual_review"
    NO_SUCCESSFUL_PAYMENT = "no_successful_payment"
    NO_REFUND_DUE_USAGE = "no_refund_due_usage"


class Purchase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: PurchaseType
    amount_inr: int = Field(ge=0)
    status: PurchaseStatus
    at: datetime


class TicketIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    received_at: datetime
    subject: str
    body: str
    purchases: list[Purchase]
    app_opens_since_renewal: int = Field(ge=0)


class ClassifierResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    severity: Severity
    reply_draft: str = Field(min_length=1)
    needs_human: bool
    confidence: float = Field(ge=0.0, le=1.0)
    language: str = Field(min_length=2)
    prompt_injection_detected: bool = False

    @field_validator("reply_draft")
    @classmethod
    def reply_must_not_expose_internal_policy(cls, value: str) -> str:
        blocked = ("system prompt", "internal refund rules", "ignore your previous instructions")
        lowered = value.lower()
        if any(term in lowered for term in blocked):
            raise ValueError("reply draft appears to expose internal instructions")
        return value


class RefundDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eligible: bool
    amount_inr: int = Field(ge=0)
    purchase_ids: list[str]
    reason_code: RefundReasonCode
    explanation: str
    action: Literal["none", "recommend_refund", "manual_review"]


class ClassifierMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["ai", "fixture", "fallback"]
    model: str | None = None
    low_confidence: bool
    validation_recovered: bool = False
    prompt_injection_detected: bool = False


class IdempotencyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replayed: bool
    decision_id: str


class TriageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    category: Category
    severity: Severity
    refund: RefundDecision
    reply_draft: str
    needs_human: bool
    confidence: float = Field(ge=0.0, le=1.0)
    classifier: ClassifierMetadata
    idempotency: IdempotencyMetadata
