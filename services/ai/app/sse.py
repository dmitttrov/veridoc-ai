"""Server-Sent Events encoding for chat stream events."""
from __future__ import annotations

from app.models import ChatStreamEvent


def encode_sse(event: ChatStreamEvent) -> str:
    """Serialize an event as a single SSE record.

    `by_alias=True` ensures field names match the TypeScript contract
    (e.g. `tokenCount`, `documentId`).
    """
    payload = event.model_dump_json(by_alias=True)
    return f"data: {payload}\n\n"
