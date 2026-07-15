"""Tool: get_equipment_details."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore
from app.tools.base import Tool


class GetEquipmentDetails(Tool):
    name = "get_equipment_details"
    description = (
        "Look up a semiconductor tool by its equipment_id (e.g. 'EQ001') or "
        "its name (e.g. 'Etcher-03'). Returns vendor, model, line/bay, process "
        "area and the primary engineer."
    )
    parameters = {
        "type": "object",
        "properties": {
            "identifier": {
                "type": "string",
                "description": "equipment_id or equipment_name",
            }
        },
        "required": ["identifier"],
    }

    # DI: the store is injected, not imported as a global.
    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def run(self, identifier: str) -> dict[str, Any]:
        row = self._store.get_equipment(identifier)
        if row is None:
            # Defensive: never raise on missing data.
            return {"found": False, "identifier": identifier}
        return {"found": True, "equipment": row}
