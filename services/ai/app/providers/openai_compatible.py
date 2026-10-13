"""OpenAI-compatible inference provider (for local servers incl. vLLM).

Talks to a local server's `/chat/completions` endpoint. It is **never** a paid
API and the internal server is never exposed to clients directly. It never
silently falls back to the mock — failures raise `InferenceError` (buffered
`generate`) or emit a terminal `error` event (`stream_chat`).

Privacy: this module never logs prompts, messages, document content, API keys,
or model responses — only coarse status/error codes.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.models import ChatRequest, ChatStreamEvent, DoneEvent, ErrorEvent, TokenEvent
from app.providers.base import ChatMessage, GenerationResult, InferenceError

logger = logging.getLogger("veridoc.ai.inference")


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("inference_base_url must be set for openai_compatible provider")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_s
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        # An injected client (tests) is reused and not closed here.
        self._client = client
        self._owns_client = client is None

    @property
    def name(self) -> str:
        return self._model

    @property
    def is_mock(self) -> bool:
        return False

    def _url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _new_client(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=self._timeout)

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int,
        temperature: float,
    ) -> GenerationResult:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        client = self._new_client()
        try:
            resp = await client.post(self._url(), json=payload, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            token_count = int(usage.get("completion_tokens") or len(str(text).split()))
            return GenerationResult(text=str(text), model=self._model, token_count=token_count)
        except httpx.TimeoutException as exc:
            raise InferenceError("Inference request timed out.", "inference_timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("inference upstream status=%s", exc.response.status_code)
            raise InferenceError(
                "The inference server returned an error.", "inference_upstream_error"
            ) from exc
        except httpx.RequestError as exc:
            raise InferenceError(
                "Could not reach the inference server.", "inference_unavailable"
            ) from exc
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise InferenceError(
                "The inference server returned a malformed response.", "inference_malformed"
            ) from exc
        finally:
            if self._owns_client:
                await client.aclose()

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        messages = [{"role": m.role, "content": m.content} for m in request.history]
        messages.append({"role": "user", "content": request.message})
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        client = self._new_client()
        token_count = 0
        try:
            async with client.stream(
                "POST", self._url(), json=payload, headers=self._headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, ValueError, TypeError):
                        continue
                    if delta:
                        token_count += 1
                        yield TokenEvent(text=delta)
            yield DoneEvent(mock=False, model=self._model, token_count=token_count)
        except httpx.TimeoutException:
            yield ErrorEvent(message="Inference request timed out.", code="inference_timeout")
        except httpx.HTTPStatusError as exc:
            logger.warning("inference stream upstream status=%s", exc.response.status_code)
            yield ErrorEvent(
                message="The inference server returned an error.",
                code="inference_upstream_error",
            )
        except httpx.RequestError:
            yield ErrorEvent(
                message="Could not reach the inference server.", code="inference_unavailable"
            )
        finally:
            if self._owns_client:
                await client.aclose()
