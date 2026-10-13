"""Provider abstraction for streaming chat inference."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.models import ChatRequest, ChatStreamEvent


@runtime_checkable
class InferenceProvider(Protocol):
    """A streaming, source-grounded chat provider.

    Implementations yield `ChatStreamEvent`s: zero or more `token` events,
    an optional `citations` event, and exactly one terminal event
    (`done` or `error`). Implementations must not raise mid-stream; recoverable
    failures should be surfaced as a terminal `error` event instead.
    """

    @property
    def name(self) -> str: ...

    @property
    def is_mock(self) -> bool: ...

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]: ...
