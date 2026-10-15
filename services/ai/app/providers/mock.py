"""Deterministic mock inference provider.

Given the same request, this always produces the same answer, citations, and
token sequence. That determinism is what makes the vertical slice testable
end-to-end without a GPU, a model, or any paid external service.

The answer is explicitly framed as mock output and never fabricates concrete
financial figures — it describes *how* a grounded answer would be assembled,
pointing at fixture citations.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from app.fixtures import citations_for
from app.models import (
    ChatRequest,
    ChatStreamEvent,
    CitationsEvent,
    DoneEvent,
    TokenEvent,
)
from app.providers.base import ChatMessage, GenerationResult

_MARKER = re.compile(r"\[(E\d+)\]")


def _build_answer(request: ChatRequest) -> str:
    """Compose a deterministic, grounded-style answer for the question."""
    question = request.message.strip()
    selected = request.document_ids
    scope = (
        f"the {len(selected)} selected document(s)"
        if selected
        else "all available sample documents"
    )
    return (
        f"[MOCK MODE] This is a deterministic placeholder answer generated "
        f"without a language model. You asked: “{question}”. "
        f"In the full system, Veridoc AI would retrieve the most relevant "
        f"passages from {scope}, then generate an answer grounded strictly in "
        f"those passages, with inline citations to the source document and page. "
        f"No real financial figures are invented here; see the attached sample "
        f"citations for where grounded evidence would appear."
    )


def _tokenize(text: str) -> list[str]:
    """Split into whitespace-delimited chunks, preserving the spaces.

    Deterministic and dependency-free; good enough to simulate streaming.
    """
    tokens: list[str] = []
    current = ""
    for ch in text:
        current += ch
        if ch == " ":
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)
    return tokens


class MockProvider:
    """A deterministic, source-grounded mock streaming provider."""

    def __init__(self, model_name: str, token_delay_s: float = 0.0) -> None:
        self._model_name = model_name
        self._token_delay_s = max(0.0, token_delay_s)

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def is_mock(self) -> bool:
        return True

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        answer = _build_answer(request)
        tokens = _tokenize(answer)

        for token in tokens:
            if self._token_delay_s:
                await asyncio.sleep(self._token_delay_s)
            yield TokenEvent(text=token)

        yield CitationsEvent(citations=citations_for(request.document_ids))

        yield DoneEvent(
            mock=True,
            model=self._model_name,
            token_count=len(tokens),
        )

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> GenerationResult:
        """Deterministic grounded generation for the RAG path.

        Produces an answer that cites the evidence markers (`[E1]`, ...) present
        in the user prompt, so the citation-verification pipeline can be fully
        exercised without a real model. It deliberately ignores any instructions
        embedded in the evidence (prompt-injection), citing evidence only.
        """
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        markers = _MARKER.findall(user)
        if not markers:
            # No evidence markers in the prompt -> signal abstention upstream.
            text = "INSUFFICIENT_EVIDENCE"
        else:
            unique = sorted(set(markers), key=lambda m: int(m[1:]))
            cited = " ".join(f"[{m}]" for m in unique[:2])
            text = (
                "[MOCK ANSWER] Based strictly on the retrieved evidence, this is a "
                f"deterministic placeholder grounded answer {cited}. No real model "
                "was used and no figures were invented."
            )
        return GenerationResult(
            text=text,
            model=self._model_name,
            token_count=len(_tokenize(text)),
        )
