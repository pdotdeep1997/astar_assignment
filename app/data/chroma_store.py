"""ChromaDB implementation of the VectorStore port.

Principle: Dependency Inversion — Chroma is a swappable detail. We inject the
EmbeddingProvider (composition over inheritance) rather than letting Chroma
own embeddings, so the SAME embedder is used everywhere and can be swapped
independently of the vector store.
"""
from __future__ import annotations

from typing import Any

from app.data.interfaces import EmbeddingProvider, VectorStore


class ChromaVectorStore(VectorStore):
    def __init__(self, path: str, embedder: EmbeddingProvider) -> None:
        import chromadb
        from chromadb.config import Settings

        # Persistent on-disk client: no server process required.
        # anonymized_telemetry=False silences Chroma's (buggy) telemetry calls
        # that otherwise log harmless "Failed to send telemetry event" warnings.
        self._client = chromadb.PersistentClient(
            path=path, settings=Settings(anonymized_telemetry=False)
        )
        self._embedder = embedder  # injected dependency (DI)
        self._collections: dict[str, Any] = {}

    def _collection(self, name: str):
        # We pass embeddings in explicitly, so Chroma's own embedding fn is off.
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
        return self._collections[name]

    def upsert(
        self,
        collection: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        embeddings = self._embedder.embed(documents)
        self._collection(collection).upsert(
            ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
        )

    def query(
        self, collection: str, text: str, n_results: int = 3
    ) -> list[dict[str, Any]]:
        query_emb = self._embedder.embed([text])[0]
        res = self._collection(collection).query(
            query_embeddings=[query_emb], n_results=n_results
        )
        # Flatten Chroma's nested result shape into a simple list of dicts.
        out: list[dict[str, Any]] = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            out.append({"document": doc, "metadata": meta, "distance": dist})
        return out

    def count(self, collection: str) -> int:
        return self._collection(collection).count()
