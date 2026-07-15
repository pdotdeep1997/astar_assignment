"""SQLite implementation of the StructuredStore port.

Principle: Dependency Inversion — this is a low-level detail that conforms to
the abstraction in interfaces.py. Nothing outside this file knows the backing
store is SQLite. Swapping to Postgres = new class, same interface.

Principle: DRY — all access goes through the private `_rows` / `_row` helpers
so query/serialisation logic lives in exactly one place.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.data.interfaces import StructuredStore


class SQLiteStore(StructuredStore):
    def __init__(self, db_path: str) -> None:
        # check_same_thread=False so FastAPI's threadpool can share the conn.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        # Return rows as dict-like objects -> decouples callers from column order.
        self._conn.row_factory = sqlite3.Row

    # --- private helpers (single source of truth for querying) -------------
    def _rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = self._conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def _row(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self._rows(sql, params)
        return rows[0] if rows else None

    # --- equipment ---------------------------------------------------------
    def get_equipment(self, identifier: str) -> dict[str, Any] | None:
        # Accept either the id or the human-friendly name (case-insensitive).
        return self._row(
            "SELECT * FROM equipment_master "
            "WHERE equipment_id = ? OR LOWER(equipment_name) = LOWER(?)",
            (identifier, identifier),
        )

    # --- alarms ------------------------------------------------------------
    def get_alarm(self, alarm_code: str) -> dict[str, Any] | None:
        return self._row(
            "SELECT * FROM alarm_reference WHERE alarm_code = ?", (alarm_code,)
        )

    # --- maintenance -------------------------------------------------------
    def get_maintenance_history(
        self, equipment_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM maintenance_records WHERE equipment_id = ? "
            "ORDER BY maintenance_date DESC LIMIT ?",
            (equipment_id, limit),
        )

    # --- sensors -----------------------------------------------------------
    def get_sensor_readings(self, incident_id: str) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT * FROM sensor_readings WHERE incident_id = ? ORDER BY timestamp",
            (incident_id,),
        )

    # --- escalation --------------------------------------------------------
    def get_escalation_rules(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM escalation_rules ORDER BY rule_id")

    def count_recent_same_alarm(
        self, equipment_id: str, alarm_code: str, before: str, days: int
    ) -> int:
        # SQLite date math: count history rows within `days` before `before`.
        row = self._row(
            "SELECT COUNT(*) AS n FROM incident_history "
            "WHERE equipment_id = ? AND alarm_code = ? "
            "AND timestamp < ? "
            "AND timestamp >= datetime(?, ?)",
            (equipment_id, alarm_code, before, before, f"-{days} days"),
        )
        return int(row["n"]) if row else 0

    def find_engineer_by_role(self, role: str) -> dict[str, Any] | None:
        # Match on role OR name so escalation targets like "Vendor Support"
        # (a name, not a role) still resolve to a concrete contact.
        return self._row(
            "SELECT * FROM engineer_directory "
            "WHERE LOWER(role) = LOWER(?) OR LOWER(name) = LOWER(?) LIMIT 1",
            (role, role),
        )

    # --- corpora for the vector index / SOP lookup -------------------------
    def get_incident_history(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM incident_history")

    def get_sops(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM sop_knowledge_base")

    def get_sop_by_alarm(self, alarm_code: str) -> dict[str, Any] | None:
        return self._row(
            "SELECT * FROM sop_knowledge_base WHERE alarm_code = ?", (alarm_code,)
        )

    def close(self) -> None:
        self._conn.close()
