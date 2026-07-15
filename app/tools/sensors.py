"""Tool: get_sensor_readings."""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore
from app.tools.base import Tool


class GetSensorReadings(Tool):
    name = "get_sensor_readings"
    description = (
        "Retrieve the time-series sensor readings (rf_power, chamber_temp, "
        "gas_flow, pressure, vibration) captured around a current incident, by "
        "incident_id (e.g. INC001). Useful for confirming an anomaly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "e.g. INC001"}
        },
        "required": ["incident_id"],
    }

    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def run(self, incident_id: str) -> dict[str, Any]:
        rows = self._store.get_sensor_readings(incident_id)
        return {"count": len(rows), "readings": rows}
