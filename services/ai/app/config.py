"""Runtime configuration, sourced from environment variables.

No secrets are hardcoded. See `.env.example` for the documented knobs.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    # Which inference provider to use: "mock" (default, deterministic) or
    # "openai_compatible" (a local OpenAI-compatible server, incl. vLLM).
    inference_provider: str = "mock"

    # Logical model identifier reported by the mock provider.
    model_name: str = "veridoc-mock-0.1"

    # --- Phase 3: real inference (OpenAI-compatible) -----------------------
    # Base URL of a local OpenAI-compatible server, e.g. http://localhost:8001/v1
    inference_base_url: str = ""
    # Model id to request from that server.
    inference_model: str = "local-model"
    # Optional API key for protected local services (never logged).
    inference_api_key: str = ""
    inference_timeout_s: float = 60.0
    inference_max_tokens: int = 512
    inference_temperature: float = 0.0

    # CORS: the AI service is internal-only and should NOT be exposed publicly.
    # It is reachable from the gateway over the private compose network.
    cors_allow_origins: list[str] = []

    # Per-token delay (seconds) to make streaming visible in local demos.
    # Deterministic content is unaffected; this only paces emission.
    stream_token_delay_s: float = 0.02

    # --- Phase 2: database -------------------------------------------------
    # PostgreSQL + pgvector connection string. Not a secret in local dev
    # (compose defaults); override via env in any real deployment.
    database_url: str = "postgresql://veridoc:veridoc@localhost:5432/veridoc"

    # --- Phase 2: embeddings ----------------------------------------------
    # "deterministic" (default; no heavy deps, reproducible) or
    # "sentence-transformers" (real local model; optional extra).
    embedding_provider: str = "deterministic"
    # Fixed vector dimensionality. The DB vector column is vector(EMBEDDING_DIM);
    # changing this requires a migration. all-MiniLM-L6-v2 is also 384-dim.
    embedding_dim: int = 384
    # Model id for the real provider (Apache-2.0 licensed, small, local).
    sentence_transformers_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Phase 3: reranking ------------------------------------------------
    # "none" (default), "deterministic" (reproducible, no deps), or
    # "cross-encoder" (real local model via the optional [embeddings] extra).
    reranker_provider: str = "none"
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Number of first-stage (RRF) candidates handed to the reranker.
    rerank_candidate_k: int = 20

    # --- Phase 2: ingestion limits & chunking -----------------------------
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MiB
    max_pages: int = 300
    pdf_parse_timeout_s: float = 30.0
    chunk_size_chars: int = 800
    chunk_overlap_chars: int = 150
    # Max PDF ingestions processed concurrently. Bounds worst-case memory
    # (~max_upload_bytes each) and CPU from a burst of uploads; excess requests
    # are rejected with 429 rather than queued (which would still buffer bodies).
    max_concurrent_ingestions: int = 2

    # --- Phase 3: generation safety ---------------------------------------
    # Defensive cap on a buffered RAG answer (characters) before it is tokenized
    # and streamed, bounding memory if a provider ignores max_tokens.
    max_answer_chars: int = 24000

    @property
    def is_mock(self) -> bool:
        return self.inference_provider == "mock"

    @property
    def embedding_model_id(self) -> str:
        """Stable identity string recorded alongside every stored embedding."""
        if self.embedding_provider == "sentence-transformers":
            return self.sentence_transformers_model
        return "veridoc-deterministic-emb-v1"


def get_settings() -> Settings:
    return Settings()
