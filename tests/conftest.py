"""Shared pytest fixtures.

Builds a real data layer (SQLite + Chroma with the offline hash embedder) from
the dataset in a temp directory, so tests exercise the genuine query/retrieval
code without any network access.
"""
from __future__ import annotations

import pytest

from app.data.chroma_store import ChromaVectorStore
from app.data.embeddings import HashEmbedder
from app.data.loader import build_vector_index, load_excel_to_sqlite
from app.data.sqlite_store import SQLiteStore
from app.container import build_tool_registry

DATASET = "data/Incident_Investigation_dataset.xlsx"


@pytest.fixture(scope="session")
def store(tmp_path_factory):
    db = tmp_path_factory.mktemp("data") / "incident.db"
    load_excel_to_sqlite(DATASET, str(db))
    return SQLiteStore(str(db))


@pytest.fixture(scope="session")
def vectors(store, tmp_path_factory):
    path = tmp_path_factory.mktemp("chroma")
    vs = ChromaVectorStore(str(path), HashEmbedder())
    build_vector_index(store, vs)
    return vs


@pytest.fixture
def registry(store, vectors):
    return build_tool_registry(store, vectors)
