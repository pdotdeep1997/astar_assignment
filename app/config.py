"""Application configuration.

Principle: 12-factor config — every environment-specific value (model, keys,
paths) comes from the environment, never from hard-coded literals. This makes
the app portable and keeps secrets out of source control.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings object (Pydantic validates types at startup)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM (Anthropic via LiteLLM). The `anthropic/` prefix tells LiteLLM which
    # provider to route to.
    llm_model: str = "claude-opus-4-8"
    anthropic_api_key: str | None = None

    # Embeddings: "local" (sentence-transformers) | "hash" (offline fallback).
    embedding_provider: str = "local"

    # Data / storage
    dataset_path: str = "data/Incident_Investigation_dataset.xlsx"
    sqlite_path: str = "data/incident.db"
    chroma_path: str = "data/chroma"

    # Agent
    max_tool_iterations: int = 8


# A single import-time instance is fine; tests can construct their own Settings.
settings = Settings()
