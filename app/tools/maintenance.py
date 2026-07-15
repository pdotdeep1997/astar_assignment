"""Tool: get_maintenance_history."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore
from app.tools.base import Tool


class GetMaintenanceHistory(Tool):
    name = "get_maintenance_history"
    description = (
        "Retrieve recent maintenance records (preventive, calibration, "
        "corrective, inspection) for a tool by equipment_id. Useful for spotting "
        "a recent PM abnormality that may explain a new alarm."
    )
    parameters = {
        "type": "object",
        "properties": {
            "equipment_id": {"type": "string", "description": "e.g. EQ001"},
            "limit": {"type": "integer", "description": "Max records (default 10)."},
        },
        "required": ["equipment_id"],
    }

    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def run(self, equipment_id: str, limit: int = 10) -> dict[str, Any]:
        rows = self._store.get_maintenance_history(equipment_id, limit=limit)
        return {"count": len(rows), "maintenance_records": rows}
