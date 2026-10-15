"""Deterministic feature-hashing embedding provider.

No heavy dependencies, fully reproducible, and — unlike random seeding — it
carries real retrieval signal: texts that share tokens map to similar vectors
(cosine similarity grows with token overlap). This makes it a faithful stand-in
for a real embedding model in tests and in the reproducible evaluation, while
remaining identical across machines and runs.

It uses SHA-1 (not Python's salted ``hash``) so results are stable across
processes and platforms.
"""
from __future__ import annotations

import hashlib
import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")

MODEL_ID = "veridoc-deterministic-emb-v1"


def _token_hash(token: str) -> int:
    return int.from_bytes(hashlib.sha1(token.encode("utf-8")).digest()[:8], "big")


class DeterministicEmbeddingProvider:
    def __init__(self, dim: int = 384) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self._dim = dim

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in _TOKEN.findall(text.lower()):
            h = _token_hash(token)
            idx = h % self._dim
            sign = 1.0 if (h >> 17) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]
