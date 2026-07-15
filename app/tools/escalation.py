"""Tool: check_escalation — a DETERMINISTIC rules engine.

Principle: keep business rules out of the LLM. Escalation decisions must be
reliable and auditable, so they are computed in code from the escalation_rules
table — not left to model judgement. The LLM calls this tool and reports its
verdict; it does not invent escalation logic.

Rules (from the dataset's escalation_rules sheet):
  R001 downtime_minutes > 30                         -> Senior Equipment Engineer
  R002 same alarm+equipment >= 2 within 7 days       -> Engineering Manager
  R003 severity == High                              -> Process Engineer
  R004 same alarm+equipment  > 3 within 30 days      -> Vendor Support
  R005 affected_lot is not null                      -> Manufacturing Supervisor
"""
from __future__ import annotations

from typing import Any

from app.data.interfaces import StructuredStore
from app.tools.base import Tool


class CheckEscalation(Tool):
    name = "check_escalation"
    description = (
        "Deterministically evaluate whether an incident needs escalation and to "
        "whom, using the plant's escalation rules. Provide the incident's "
        "downtime, alarm severity, equipment_id, alarm_code, timestamp and "
        "affected_lot. Returns every triggered rule with its target contact."
    )
    parameters = {
        "type": "object",
        "properties": {
            "equipment_id": {"type": "string"},
            "alarm_code": {"type": "string"},
            "timestamp": {
                "type": "string",
                "description": "Incident time 'YYYY-MM-DD HH:MM' (for recurrence checks).",
            },
            "downtime_minutes": {"type": "number"},
            "severity": {"type": "string", "description": "Low | Medium | High"},
            "affected_lot": {"type": "string", "description": "Lot id, or empty."},
        },
        "required": ["equipment_id", "alarm_code", "downtime_minutes", "severity"],
    }

    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def run(
        self,
        equipment_id: str,
        alarm_code: str,
        downtime_minutes: float,
        severity: str,
        timestamp: str | None = None,
        affected_lot: str | None = None,
    ) -> dict[str, Any]:
        triggered: list[dict[str, Any]] = []

        # Recurrence counts (only computable if we know the incident time).
        recent_7 = recent_30 = 0
        if timestamp:
            recent_7 = self._store.count_recent_same_alarm(
                equipment_id, alarm_code, timestamp, days=7
            )
            recent_30 = self._store.count_recent_same_alarm(
                equipment_id, alarm_code, timestamp, days=30
            )

        # Evaluate each rule explicitly (readable > clever).
        if downtime_minutes > 30:
            triggered.append(self._rule("R001", "Senior Equipment Engineer",
                                        "Downtime exceeds 30 minutes"))
        if recent_7 >= 2:
            triggered.append(self._rule("R002", "Engineering Manager",
                                        f"Repeated alarm {recent_7}x within 7 days"))
        if severity.strip().lower() == "high":
            triggered.append(self._rule("R003", "Process Engineer",
                                        "High severity alarm may affect quality"))
        if recent_30 > 3:
            triggered.append(self._rule("R004", "Vendor Support",
                                        f"Recurring {recent_30}x within 30 days"))
        if affected_lot:
            triggered.append(self._rule("R005", "Manufacturing Supervisor",
                                        "Production lot impact requires ops visibility"))

        return {
            "escalation_required": len(triggered) > 0,
            "recent_same_alarm_7d": recent_7,
            "recent_same_alarm_30d": recent_30,
            "triggered_rules": triggered,
        }

    def _rule(self, rule_id: str, target_role: str, rationale: str) -> dict[str, Any]:
        """Resolve a rule's target role to a real contact (DRY helper)."""
        contact = self._store.find_engineer_by_role(target_role)
        return {
            "rule_id": rule_id,
            "escalation_target": target_role,
            "rationale": rationale,
            "contact": contact,  # None if directory has no match; caller handles
        }
