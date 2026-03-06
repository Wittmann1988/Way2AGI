"""
Structured JSON logger for Way2AGI Python modules.
Outputs one JSON object per line (JSONL) to stdout.
Respects LOG_LEVEL env var (default: "info").
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def __init__(self, module_name: str):
        super().__init__()
        self._module = module_name

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "module": self._module,
            "message": record.getMessage(),
        }
        meta = getattr(record, "metadata", None)
        if meta:
            entry["metadata"] = meta
        return json.dumps(entry)


def create_logger(module: str) -> logging.Logger:
    """Create a structured JSON logger for the given module."""
    logger = logging.getLogger(f"way2agi.{module}")
    if logger.handlers:
        return logger

    level = os.environ.get("LOG_LEVEL", "info").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter(module))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _log_with_meta(logger: logging.Logger, level: int, msg: str, **metadata: object) -> None:
    """Helper to log with metadata dict."""
    logger.log(level, msg, extra={"metadata": metadata} if metadata else {})


# Convenience: attach metrics method
def metrics(logger: logging.Logger, name: str, value: float, **meta: object) -> None:
    """Record a numeric metric."""
    _log_with_meta(logger, logging.INFO, f"metric:{name}", metric_name=name, metric_value=value, **meta)
