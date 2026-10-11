from pathlib import Path

import pytest

from dhaba_triage.factory import build_service
from dhaba_triage.settings import Settings


def test_settings_default_to_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DHABA_TRIAGE_DB", raising=False)
    monkeypatch.delenv("DHABA_CLASSIFIER_MODE", raising=False)
    monkeypatch.delenv("DHABA_AI_MODEL", raising=False)

    settings = Settings.from_env()

    assert settings.database_path == "triage.sqlite3"
    assert settings.classifier_mode == "fixture"
    assert settings.ai_model is None


def test_settings_read_database_and_classifier_mode_from_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "triage.sqlite3"
    monkeypatch.setenv("DHABA_TRIAGE_DB", str(db_path))
    monkeypatch.setenv("DHABA_CLASSIFIER_MODE", "fixture")
    monkeypatch.setenv("DHABA_AI_MODEL", "example-model")

    settings = Settings.from_env()

    assert settings.database_path == str(db_path)
    assert settings.classifier_mode == "fixture"
    assert settings.ai_model == "example-model"


def test_invalid_classifier_mode_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DHABA_CLASSIFIER_MODE", "magic")

    with pytest.raises(ValueError, match="DHABA_CLASSIFIER_MODE"):
        Settings.from_env()


def test_ai_mode_requires_configured_model_client(tmp_path: Path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "triage.sqlite3"),
        classifier_mode="ai",
        ai_model="example-model",
    )

    with pytest.raises(RuntimeError, match="AI classifier mode"):
        build_service(settings)
