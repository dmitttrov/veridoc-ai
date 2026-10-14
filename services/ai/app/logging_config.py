"""Structured (JSON-per-line) application logging with request-id correlation.

The gateway forwards an ``x-request-id`` on every call; a middleware binds it to
a context variable so every log line emitted while handling that request carries
the same id, and the gateway's logs for the request can be joined to ours.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER = "x-request-id"

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def sanitize_request_id(value: str | None) -> str | None:
    """Only accept a short, safe inbound id (it is logged + reflected)."""
    if value is None:
        return None
    value = value.strip()
    return value if _SAFE_ID.match(value) else None


def new_request_id() -> str:
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            entry["requestId"] = request_id
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
