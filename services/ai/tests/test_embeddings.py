import math

import pytest

from app.config import Settings
from app.embeddings import build_embedding_provider
from app.embeddings.deterministic import DeterministicEmbeddingProvider


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def test_deterministic_and_correct_dim() -> None:
    p = DeterministicEmbeddingProvider(dim=384)
    v1 = p.embed(["total revenue was 482.6 million"])[0]
    v2 = p.embed(["total revenue was 482.6 million"])[0]
    assert v1 == v2
    assert len(v1) == 384


def test_unit_norm() -> None:
    p = DeterministicEmbeddingProvider(dim=384)
    v = p.embed(["research and development expenses"])[0]
    assert abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-9


def test_token_overlap_increases_similarity() -> None:
    p = DeterministicEmbeddingProvider(dim=384)
    base = p.embed(["acme robotics total revenue fiscal year"])[0]
    similar = p.embed(["total revenue for acme robotics this fiscal year"])[0]
    unrelated = p.embed(["weather forecast rainfall humidity temperature"])[0]
    assert _cosine(base, similar) > _cosine(base, unrelated)


def test_empty_text_is_zero_vector() -> None:
    p = DeterministicEmbeddingProvider(dim=384)
    v = p.embed([""])[0]
    assert all(x == 0.0 for x in v)


def test_factory_rejects_unsupported_dim() -> None:
    # The DB column is fixed at vector(384); a mismatched AI_EMBEDDING_DIM must
    # fail fast at startup, not deep inside the first insert.
    with pytest.raises(ValueError, match="384"):
        build_embedding_provider(Settings(embedding_provider="deterministic", embedding_dim=128))


def test_factory_builds_supported_dim() -> None:
    provider = build_embedding_provider(
        Settings(embedding_provider="deterministic", embedding_dim=384)
    )
    assert provider.dim == 384


def test_factory_enforces_dimension() -> None:
    # A provider reporting a different dim than the configured (supported) dim
    # must raise — assert the guard directly with a bogus provider.
    class Bogus:
        model_id = "bogus"
        dim = 999

        def embed(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 999 for _ in texts]

    from app.embeddings import factory

    monkey = Settings(embedding_provider="deterministic", embedding_dim=384)
    orig = factory.DeterministicEmbeddingProvider
    try:
        factory.DeterministicEmbeddingProvider = lambda dim: Bogus()  # type: ignore[assignment,misc]
        with pytest.raises(ValueError, match="dim"):
            build_embedding_provider(monkey)
    finally:
        factory.DeterministicEmbeddingProvider = orig  # type: ignore[assignment]


def test_unknown_provider_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        build_embedding_provider(Settings(embedding_provider="nope"))
