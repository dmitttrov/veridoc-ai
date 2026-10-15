"""Provider abstraction for chat inference (streaming + buffered generation)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.models import ChatRequest, ChatStreamEvent


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    token_count: int


@runtime_checkable
class InferenceProvider(Protocol):
    """A chat provider.

    `stream_chat` powers the simple (Phase 1) chat path. `generate` returns a
    complete buffered response and powers grounded RAG, where the answer must be
    validated (citation checking) BEFORE anything is shown to the user.

    Implementations must not raise mid-stream in `stream_chat`; recoverable
    failures should be surfaced as a terminal `error` event. `generate` may
    raise `InferenceError` on failure.
    """

    @property
    def name(self) -> str: ...

    @property
    def is_mock(self) -> bool: ...

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]: ...

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> GenerationResult: ...


class InferenceError(Exception):
    """A recoverable inference failure (timeout, connection, malformed response)."""

    def __init__(self, message: str, code: str = "inference_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code
