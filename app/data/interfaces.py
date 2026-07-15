"""Storage abstractions (ports).

Principle: Dependency Inversion + Interface Segregation.
High-level code (tools, agent) depends ONLY on these abstract interfaces,
never on SQLite or ChromaDB directly. To swap SQLite for Postgres, or Chroma
for Qdrant, you write a new class implementing the same interface and change
one line in the composition root (container.py) — no tool or agent code changes.

Each interface is deliberately small (Interface Segregation): a store exposes
only the query shapes its consumers actually need.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StructuredStore(ABC):
    """Port for the relational/structured dataset.

    Implementations: SQLiteStore (default). Any future PostgresStore /
    DuckDBStore only needs to satisfy these methods.
    Each method returns plain dicts/lists so callers never depend on a
    particular DB driver's row types.
    """

    # --- equipment ---------------------------------------------------------
    @abstractmethod
    def get_equipment(self, identifier: str) -> dict[str, Any] | None:
        """Look up one tool by equipment_id OR equipment_name. None if absent."""

    # --- alarms ------------------------------------------------------------
    @abstractmethod
    def get_alarm(self, alarm_code: str) -> dict[str, Any] | None:
        """Alarm reference row by code. None if the code is unknown."""

    # --- maintenance -------------------------------------------------------
    @abstractmethod
    def get_maintenance_history(
        self, equipment_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Most-recent maintenance records for a tool (newest first)."""

    # --- sensors -----------------------------------------------------------
    @abstractmethod
    def get_sensor_readings(self, incident_id: str) -> list[dict[str, Any]]:
        """Time-series sensor rows around an incident."""

    # --- escalation --------------------------------------------------------
    @abstractmethod
    def get_escalation_rules(self) -> list[dict[str, Any]]:
        """All escalation rules."""

    @abstractmethod
    def count_recent_same_alarm(
        self, equipment_id: str, alarm_code: str, before: str, days: int
    ) -> int:
        """Count prior incidents of the same alarm on the same tool within
        `days` before the `before` timestamp — used for recurrence detection."""

    @abstractmethod
    def find_engineer_by_role(self, role: str) -> dict[str, Any] | None:
        """Resolve an escalation target role to a concrete contact."""

    # --- incident history (also the corpus for the vector index) ----------
    @abstractmethod
    def get_incident_history(self) -> list[dict[str, Any]]:
        """All historical incidents (used to build the similarity index)."""

    @abstractmethod
    def get_sops(self) -> list[dict[str, Any]]:
        """All SOP rows (used to build the SOP index and for exact lookup)."""

    @abstractmethod
    def get_sop_by_alarm(self, alarm_code: str) -> dict[str, Any] | None:
        """Exact SOP lookup by alarm code (fast path before semantic search)."""


class EmbeddingProvider(ABC):
    """Port for turning text into vectors.

    Principle: Strategy pattern — local sentence-transformers or a hashing
    fallback are interchangeable behind this one method.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class VectorStore(ABC):
    """Port for semantic search over a named collection.

    Implementations: ChromaVectorStore (default). Swappable for Qdrant/FAISS.
    """

    @abstractmethod
    def upsert(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add or update documents in a collection."""

    @abstractmethod
    def query(
        self, collection: str, text: str, n_results: int = 3
    ) -> list[dict[str, Any]]:
        """Return the top-n most similar documents with their metadata."""

    @abstractmethod
    def count(self, collection: str) -> int:
        """Number of documents currently in a collection (for idempotent load)."""
