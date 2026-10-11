import json

from dhaba_triage.classifier import ModelBackedClassifier
from dhaba_triage.schemas import Category, TicketIn


class FakeModelClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _ticket() -> TicketIn:
    return TicketIn.model_validate(
        {
            "id": "T-test",
            "received_at": "2026-09-02T09:14:00+05:30",
            "subject": "charged 249 without telling me",
            "body": "refund it please",
            "purchases": [
                {
                    "id": "pay_1",
                    "type": "renewal",
                    "amount_inr": 249,
                    "status": "successful",
                    "at": "2026-09-01T20:04:00+05:30",
                }
            ],
            "app_opens_since_renewal": 0,
        }
    )


def _valid_payload() -> str:
    return json.dumps(
        {
            "category": "billing_refund",
            "severity": "medium",
            "reply_draft": "Thanks for contacting us. We will review the payment.",
            "needs_human": False,
            "confidence": 0.84,
            "language": "en",
            "prompt_injection_detected": False,
        }
    )


def test_model_classifier_accepts_json_wrapped_in_prose() -> None:
    client = FakeModelClient([f"Here is the JSON:\n{_valid_payload()}"])

    envelope = ModelBackedClassifier(client, model="fake-model").classify(_ticket())

    assert envelope.result.category == Category.BILLING_REFUND
    assert envelope.validation_recovered is False


def test_model_classifier_retries_after_invalid_output() -> None:
    client = FakeModelClient(["not json", _valid_payload()])

    envelope = ModelBackedClassifier(client, model="fake-model").classify(_ticket())

    assert envelope.result.category == Category.BILLING_REFUND
    assert envelope.validation_recovered is True
    assert len(client.prompts) == 2
    assert "previous response failed validation" in client.prompts[1].lower()


def test_model_classifier_falls_back_after_repeated_invalid_output() -> None:
    client = FakeModelClient(
        [
            json.dumps({"category": "invented", "severity": "medium"}),
            "still not valid",
        ]
    )

    envelope = ModelBackedClassifier(client, model="fake-model").classify(_ticket())

    assert envelope.mode == "fallback"
    assert envelope.result.category == Category.UNKNOWN
    assert envelope.result.needs_human is True
    assert envelope.result.confidence == 0.0
