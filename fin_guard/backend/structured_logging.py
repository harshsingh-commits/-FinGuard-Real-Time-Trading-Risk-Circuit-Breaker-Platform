"""Structured JSON logging for production observability."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "logger": record.name, "event": record.getMessage()})


def get_logger(name: str = "finguard") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger