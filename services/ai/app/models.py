"""Pydantic models mirroring `@veridoc/contracts`.

These are intentionally kept in lock-step with the TypeScript zod schemas.
Any change here must be reflected in packages/contracts/src/index.ts.

Wire format is camelCase (matching the TS contract); Python code uses
snake_case field names. A shared `alias_generator` bridges the two so we
never hand-maintain per-field aliases. Constrained fields use `Annotated`
metadata (pydantic's recommended form when an alias generator is in play).
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

CONTRACTS_VERSION = "0.1.0"


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        protected_namespaces=(),  # allow a field literally named `model`
    )


class ChatMessage(CamelModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=8000)]


class ChatRequest(CamelModel):
    message: Annotated[str, Field(min_length=1, max_length=8000)]
    history: Annotated[list[ChatMessage], Field(default_factory=list, max_length=50)]
    document_ids: Annotated[list[str], Field(default_factory=list, max_length=50)]


class DocumentSummary(CamelModel):
    id: str
    title: str
    issuer: str
    period: str
    page_count: Annotated[int, Field(gt=0)]


class Citation(CamelModel):
    document_id: str
    document_title: str
    page: Annotated[int, Field(gt=0)]
    snippet: Annotated[str, Field(min_length=1)]


# --- Streaming events (discriminated union on `type`) ----------------------


class TokenEvent(CamelModel):
    type: Literal["token"] = "token"
    text: str


class CitationsEvent(CamelModel):
    type: Literal["citations"] = "citations"
    citations: list[Citation]


class DoneEvent(CamelModel):
    type: Literal["done"] = "done"
    mock: bool
    model: str
    token_count: Annotated[int, Field(ge=0)]


class ErrorEvent(CamelModel):
    type: Literal["error"] = "error"
    message: str
    code: str


ChatStreamEvent = Annotated[
    TokenEvent | CitationsEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]


class HealthStatus(CamelModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    mock: bool | None = None
