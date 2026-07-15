"""Embedding strategies implementing the EmbeddingProvider port.

Principle: new embedding backends can be added
without touching consumers. `build_embedder` (a small factory) selects one
from config so the rest of the app stays provider-agnostic.

Two strategies (Anthropic has no embeddings API, so embeddings are local):
  * local  -> sentence-transformers (good quality, offline after first download)
  * hash   -> deterministic bag-of-words hashing (zero deps/network; for CI)
"""
from __future__ import annotations

import hashlib
import math
import re

from app.data.interfaces import EmbeddingProvider


class LocalEmbedder(EmbeddingProvider):
    """sentence-transformers all-MiniLM-L6-v2. Lazy-loads the model once."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Imported lazily so the dependency is only required when actually used.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


class HashEmbedder(EmbeddingProvider):
    """Deterministic hashing embedder — no model, no network.

    Not as semantically rich as a neural model, but good enough for tests and
    guarantees the app runs fully offline. Uses hashed token counts projected
    into a fixed-dimension L2-normalised vector.
    """

    def __init__(self, dim: int = 256) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self._dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def build_embedder(provider: str) -> EmbeddingProvider:
    """Factory selecting an embedder from a config string."""
    provider = provider.lower()
    if provider == "local":
        return LocalEmbedder()
    if provider == "hash":
        return HashEmbedder()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")
