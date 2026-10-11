from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any


GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b")
PAYMENT_ID_RE = re.compile(r"\bpay_[A-Za-z0-9]+\b")
EMAIL_RE = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        redacted = GSTIN_RE.sub("[REDACTED_GSTIN]", value)
        redacted = PAYMENT_ID_RE.sub("[REDACTED_PAYMENT_ID]", redacted)
        redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def safe_extra(**fields: Any) -> dict[str, Any]:
    return {"event": redact(fields)}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if isinstance(event, dict):
            payload.update(redact(event))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("dhaba_triage")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
