from __future__ import annotations

from dhaba_triage.classifier import FixtureClassifier
from dhaba_triage.service import TriageService
from dhaba_triage.settings import Settings
from dhaba_triage.store import DecisionStore


def build_service(settings: Settings) -> TriageService:
    if settings.classifier_mode == "fixture":
        classifier = FixtureClassifier()
    else:
        raise RuntimeError(
            "AI classifier mode needs a configured model client. "
            "Use DHABA_CLASSIFIER_MODE=fixture to run without credentials."
        )

    return TriageService(
        classifier=classifier,
        store=DecisionStore(settings.database_path),
    )
