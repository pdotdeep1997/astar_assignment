"""Tool: get_alarm_details."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore
from app.tools.base import Tool


class GetAlarmDetails(Tool):
    name = "get_alarm_details"
    description = (
        "Look up an alarm code (e.g. 'RF101') to get its severity, description, "
        "probable causes and the tool type it applies to."
    )
    parameters = {
        "type": "object",
        "properties": {
            "alarm_code": {"type": "string", "description": "Alarm code, e.g. RF101"}
        },
        "required": ["alarm_code"],
    }

    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def run(self, alarm_code: str) -> dict[str, Any]:
        row = self._store.get_alarm(alarm_code)
        if row is None:
            return {"found": False, "alarm_code": alarm_code}
        return {"found": True, "alarm": row}
