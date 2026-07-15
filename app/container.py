"""Composition root — the ONE place where concrete implementations are chosen
and wired together.

Principle: Dependency Injection / Composition Root pattern. Every other module
depends on abstractions; only this file names concrete classes (SQLiteStore,
ChromaVectorStore, LiteLLMClient, ...). To swap a backing technology you edit
exactly one line here and nothing else — the promised "swap the database
easily" property.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agent.loop import InvestigationAgent
from app.config import Settings
from app.data.chroma_store import ChromaVectorStore
from app.data.embeddings import build_embedder
from app.data.interfaces import EmbeddingProvider, StructuredStore, VectorStore
from app.data.loader import build_vector_index, load_excel_to_sqlite
from app.data.sqlite_store import SQLiteStore
from app.llm.interfaces import LLMClient
from app.llm.litellm_client import LiteLLMClient
from app.tools.alarms import GetAlarmDetails
from app.tools.base import ToolRegistry
from app.tools.equipment import GetEquipmentDetails
from app.tools.escalation import CheckEscalation
from app.tools.incidents import GetSimilarIncidents
from app.tools.maintenance import GetMaintenanceHistory
from app.tools.sensors import GetSensorReadings
from app.tools.sop import GetSOP


@dataclass
class Container:
    """Holds the wired-up singletons for the app's lifetime."""

    store: StructuredStore
    embedder: EmbeddingProvider
    vectors: VectorStore
    llm: LLMClient
    registry: ToolRegistry
    agent: InvestigationAgent


def build_tool_registry(
    store: StructuredStore, vectors: VectorStore
) -> ToolRegistry:
    """Register every tool with its injected dependencies (DI in action)."""
    registry = ToolRegistry()
    registry.register(GetEquipmentDetails(store))
    registry.register(GetAlarmDetails(store))
    registry.register(GetSimilarIncidents(vectors))
    registry.register(GetMaintenanceHistory(store))
    registry.register(GetSensorReadings(store))
    registry.register(GetSOP(store, vectors))
    registry.register(CheckEscalation(store))
    return registry


def build_container(settings: Settings) -> Container:
    """Wire the whole graph from configuration.

    Swap points (each is a single line):
      * StructuredStore  -> replace SQLiteStore with e.g. PostgresStore
      * VectorStore      -> replace ChromaVectorStore with e.g. QdrantStore
      * EmbeddingProvider-> chosen by settings.embedding_provider
      * LLMClient        -> replace LiteLLMClient with any LLMClient impl
    """
    # 1. Prepare data (idempotent; safe on every startup).
    load_excel_to_sqlite(settings.dataset_path, settings.sqlite_path)

    # 2. Concrete stores (the only place these classes are named).
    store: StructuredStore = SQLiteStore(settings.sqlite_path)
    embedder: EmbeddingProvider = build_embedder(settings.embedding_provider)
    vectors: VectorStore = ChromaVectorStore(settings.chroma_path, embedder)

    # 3. Build semantic indexes (idempotent).
    build_vector_index(store, vectors)

    # 4. LLM + agent (Anthropic via LiteLLM).
    llm: LLMClient = LiteLLMClient(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
    )
    registry = build_tool_registry(store, vectors)
    agent = InvestigationAgent(llm, registry, max_iterations=settings.max_tool_iterations)

    return Container(
        store=store,
        embedder=embedder,
        vectors=vectors,
        llm=llm,
        registry=registry,
        agent=agent,
    )
