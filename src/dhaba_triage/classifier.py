from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from dhaba_triage.schemas import Category, ClassifierResult, Severity, TicketIn


LOW_CONFIDENCE_THRESHOLD = 0.65


@dataclass(frozen=True)
class ClassifierEnvelope:
    result: ClassifierResult
    mode: str
    model: str | None = None
    validation_recovered: bool = False


class FixtureClassifier:
    """Deterministic classifier used for local evaluation without model credentials."""

    mode = "fixture"
    model = None

    def classify(self, ticket: TicketIn) -> ClassifierEnvelope:
        text = f"{ticket.subject}\n{ticket.body}".lower()
        prompt_injection = _detect_prompt_injection(text)

        try:
            result = ClassifierResult(
                category=_category_for(text, ticket),
                severity=_severity_for(text, ticket, prompt_injection),
                reply_draft=_reply_for(text, ticket),
                needs_human=_needs_human(text, ticket, prompt_injection),
                confidence=_confidence_for(text, ticket, prompt_injection),
                language=_language_for(text),
                prompt_injection_detected=prompt_injection,
            )
            return ClassifierEnvelope(result=result, mode=self.mode, model=self.model)
        except ValidationError:
            fallback = ClassifierResult(
                category=Category.UNKNOWN,
                severity=Severity.MEDIUM,
                reply_draft=(
                    "Thanks for writing in. We could not safely classify this automatically, "
                    "so a support teammate will review it."
                ),
                needs_human=True,
                confidence=0.0,
                language="en",
                prompt_injection_detected=prompt_injection,
            )
            return ClassifierEnvelope(
                result=fallback,
                mode="fallback",
                model=None,
                validation_recovered=True,
            )


def _detect_prompt_injection(text: str) -> bool:
    markers = (
        "system note",
        "support assistant",
        "automated agent",
        "ignore your previous instructions",
        "system prompt",
        "internal refund rules",
        "mark this ticket resolved",
    )
    return any(marker in text for marker in markers)


def _category_for(text: str, ticket: TicketIn) -> Category:
    if "invoice" in text or "gst" in text or "gstin" in text:
        return Category.INVOICE_REQUEST
    if "offline" in text and not ticket.purchases:
        return Category.PRE_SALES_QUESTION
    if "marathi" in text or "feature request" in text:
        return Category.FEATURE_REQUEST
    if "restore" in text or "order history" in text or "changed my phone" in text:
        return Category.ACCOUNT_ACCESS
    if "crash" in text or "closes immediately" in text:
        return Category.TECHNICAL_ISSUE
    if "fraud" in text or "never installed" in text or "cyber cell" in text:
        return Category.FRAUD_OR_UNAUTHORIZED
    if "activate" in text or "free version" in text or "paisa kat" in text:
        return Category.BILLING_ACTIVATION_ISSUE
    if "cancel" in text and "refund" not in text and "charged" not in text:
        return Category.CANCELLATION
    if "refund" in text or "charged" in text or "reverse" in text or "double charge" in text:
        return Category.BILLING_REFUND
    if "worst app" in text or "1 star" in text:
        return Category.GENERAL_COMPLAINT
    return Category.UNKNOWN


def _severity_for(text: str, ticket: TicketIn, prompt_injection: bool) -> Severity:
    if "cyber cell" in text or "fraud" in text:
        return Severity.URGENT
    if prompt_injection:
        return Severity.HIGH
    if "crash" in text or "does not work" in text or "not used" in text:
        return Severity.HIGH
    if "refund" in text or "charged" in text or "activate" in text:
        return Severity.MEDIUM
    if not ticket.purchases:
        return Severity.LOW
    return Severity.MEDIUM


def _needs_human(text: str, ticket: TicketIn, prompt_injection: bool) -> bool:
    if prompt_injection:
        return True
    if "fraud" in text or "never installed" in text or "cyber cell" in text:
        return True
    if len(ticket.subject.strip()) <= 6 and len(ticket.body.strip()) <= 12:
        return True
    if "screenshot" in text:
        return True
    return False


def _confidence_for(text: str, ticket: TicketIn, prompt_injection: bool) -> float:
    if prompt_injection:
        return 0.6
    if len(ticket.subject.strip()) <= 6 and len(ticket.body.strip()) <= 12:
        return 0.45
    if "paisa kat" in text or "bhai" in text:
        return 0.78
    if not ticket.purchases and "offline" in text:
        return 0.9
    return 0.82


def _language_for(text: str) -> str:
    hinglish_markers = ("paisa", "kat gaya", "bhai", "jaldi")
    if any(marker in text for marker in hinglish_markers):
        return "hinglish"
    return "en"


def _reply_for(text: str, ticket: TicketIn) -> str:
    if "paisa kat" in text or "bhai" in text:
        return (
            "Hi, samajh gaya. Hum payment status check kar rahe hain. Agar bank se amount "
            "deduct hua hai but plan active nahi hua, toh hum activation ya reversal mein help karenge."
        )
    if "cancel" == ticket.subject.strip().lower() and ticket.body.strip().lower() == "cancel":
        return "Thanks for writing in. We can help with cancellation; a support teammate will confirm the next step."
    if "invoice" in text or "gst" in text:
        return "Thanks. We can help with the GST invoice for your annual payment and will use the billing details you shared."
    if "offline" in text:
        return "Thanks for checking before subscribing. Premium offline support depends on the feature area; we will confirm the details for you."
    if "marathi" in text:
        return "Thanks for the suggestion. We have noted your request for Marathi language support."
    if "fraud" in text or "never installed" in text:
        return "We are sorry for the concern. We will escalate this for manual review and verify the charges before any action is taken."
    if "crash" in text:
        return "Sorry about the crash. We will treat this as a technical issue and check the app version and device details you shared."
    if "refund" in text or "charged" in text or "reverse" in text:
        return "Thanks for contacting us. We will review the payment history and usage, then help with the eligible refund path."
    return "Thanks for writing in. We will review your request and get back with the next step."
