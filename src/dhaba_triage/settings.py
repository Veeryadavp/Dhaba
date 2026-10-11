from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field


ClassifierMode = Literal["fixture", "ai"]


class Settings(BaseModel):
    database_path: str = Field(default="triage.sqlite3")
    classifier_mode: ClassifierMode = Field(default="fixture")
    ai_model: str | None = Field(default=None)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DHABA_TRIAGE_DB", "triage.sqlite3"),
            classifier_mode=_classifier_mode_from_env(),
            ai_model=os.getenv("DHABA_AI_MODEL"),
        )


def _classifier_mode_from_env() -> ClassifierMode:
    raw = os.getenv("DHABA_CLASSIFIER_MODE", "fixture").strip().lower()
    if raw not in {"fixture", "ai"}:
        raise ValueError("DHABA_CLASSIFIER_MODE must be 'fixture' or 'ai'")
    return raw  # type: ignore[return-value]
