"""Runtime configuration, sourced from environment variables.

No secrets are hardcoded. See `.env.example` for the documented knobs.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    # Which inference provider to use. Phase 1 only ships "mock".
    # Future: "openai" (OpenAI-compatible, incl. a local vLLM server).
    provider: str = "mock"

    # Logical model identifier reported in responses and health checks.
    model_name: str = "veridoc-mock-0.1"

    # CORS: the AI service is internal-only and should NOT be exposed publicly.
    # It is reachable from the gateway over the private compose network.
    cors_allow_origins: list[str] = []

    # Per-token delay (seconds) to make streaming visible in local demos.
    # Deterministic content is unaffected; this only paces emission.
    stream_token_delay_s: float = 0.02

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"


def get_settings() -> Settings:
    return Settings()
