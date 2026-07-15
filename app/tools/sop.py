"""Tool: get_sop — exact-by-alarm fast path, semantic fallback."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore, VectorStore
from app.tools.base import Tool


class GetSOP(Tool):
    name = "get_sop"
    description = (
        "Retrieve the Standard Operating Procedure (troubleshooting steps) for "
        "an alarm. If an alarm_code is known, pass it for an exact match; "
        "otherwise pass a symptom description for semantic search."
    )
    parameters = {
        "type": "object",
        "properties": {
            "alarm_code": {
                "type": "string",
                "description": "Exact alarm code, e.g. RF101 (preferred if known).",
            },
            "symptom": {
                "type": "string",
                "description": "Free-text symptom, used if alarm_code is unknown.",
            },
        },
    }

    # DI: both stores injected; the tool composes them.
    def __init__(self, store: StructuredStore, vectors: VectorStore) -> None:
        self._store = store
        self._vectors = vectors

    def run(
        self, alarm_code: str | None = None, symptom: str | None = None
    ) -> dict[str, Any]:
        # Fast, deterministic path first (prefer exact over fuzzy).
        if alarm_code:
            sop = self._store.get_sop_by_alarm(alarm_code)
            if sop:
                return {"found": True, "match": "exact", "sop": sop}
        # Semantic fallback.
        query = symptom or alarm_code or ""
        if query:
            hits = self._vectors.query("sops", query, n_results=1)
            if hits:
                return {"found": True, "match": "semantic", "sop": hits[0]}
        return {"found": False, "alarm_code": alarm_code, "symptom": symptom}
