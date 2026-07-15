"""Tool: get_similar_incidents (semantic / vector search)."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import VectorStore
from app.tools.base import Tool


class GetSimilarIncidents(Tool):
    name = "get_similar_incidents"
    description = (
        "Find historically similar past incidents using semantic search over "
        "the incident history. Provide a natural-language description of the "
        "current problem (optionally include the alarm code and equipment). "
        "Returns past root causes and corrective actions to learn from."
    )
    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Free-text description of the current incident/symptoms.",
            },
            "n_results": {
                "type": "integer",
                "description": "How many similar incidents to return (default 3).",
            },
        },
        "required": ["description"],
    }

    # DI: depends on the VectorStore abstraction, not on ChromaDB.
    def __init__(self, vectors: VectorStore) -> None:
        self._vectors = vectors

    def run(self, description: str, n_results: int = 3) -> dict[str, Any]:
        hits = self._vectors.query("incidents", description, n_results=n_results)
        return {"count": len(hits), "similar_incidents": hits}
