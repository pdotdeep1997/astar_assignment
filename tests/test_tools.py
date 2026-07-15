"""Unit tests for the tools — pure functions over the real data layer.

These prove retrieval correctness and the deterministic escalation rules
WITHOUT any LLM, which is the point of keeping business logic out of the model.
"""
from __future__ import annotations

from app.tools.alarms import GetAlarmDetails
from app.tools.equipment import GetEquipmentDetails
from app.tools.escalation import CheckEscalation
from app.tools.incidents import GetSimilarIncidents
from app.tools.sensors import GetSensorReadings
from app.tools.sop import GetSOP


def test_equipment_lookup_by_id_and_name(store):
    tool = GetEquipmentDetails(store)
    assert tool.run(identifier="EQ001")["equipment"]["equipment_name"] == "Etcher-03"
    # Name lookup resolves to the same tool.
    assert tool.run(identifier="Etcher-03")["equipment"]["equipment_id"] == "EQ001"


def test_unknown_equipment_is_graceful(store):
    tool = GetEquipmentDetails(store)
    assert tool.run(identifier="ALPHA-99") == {"found": False, "identifier": "ALPHA-99"}


def test_unknown_alarm_is_graceful(store):
    tool = GetAlarmDetails(store)
    assert tool.run(alarm_code="ZX999")["found"] is False


def test_alarm_severity(store):
    tool = GetAlarmDetails(store)
    assert tool.run(alarm_code="RF101")["alarm"]["severity"] == "High"


def test_sensor_readings_present(store):
    tool = GetSensorReadings(store)
    out = tool.run(incident_id="INC001")
    assert out["count"] > 0


def test_sop_exact_match_preferred(store, vectors):
    tool = GetSOP(store, vectors)
    out = tool.run(alarm_code="RF101")
    assert out["found"] and out["match"] == "exact"


def test_similar_incidents_returns_hits(vectors):
    tool = GetSimilarIncidents(vectors)
    out = tool.run(description="RF power instability on the etcher", n_results=3)
    assert out["count"] >= 1


# --- escalation truth table (the deterministic core) -----------------------


def test_escalation_recurrence_triggers_manager(store):
    """INC001 / EQ001 / RF101 at 2026-06-22 has H101-H103 in the prior 7 days
    -> R002 must fire and target the Engineering Manager."""
    tool = CheckEscalation(store)
    out = tool.run(
        equipment_id="EQ001",
        alarm_code="RF101",
        timestamp="2026-06-22 10:35",
        downtime_minutes=45,
        severity="High",
        affected_lot="LOT1055",
    )
    assert out["escalation_required"] is True
    assert out["recent_same_alarm_7d"] >= 2
    rules = {r["rule_id"] for r in out["triggered_rules"]}
    assert "R002" in rules  # recurrence
    assert "R001" in rules  # downtime > 30
    assert "R003" in rules  # high severity


def test_escalation_low_severity_no_overescalation(store):
    """Litho alignment: low severity, 12 min, no recurrence -> only the lot
    rule may fire; must NOT trigger downtime/severity/recurrence escalations."""
    tool = CheckEscalation(store)
    out = tool.run(
        equipment_id="EQ004",
        alarm_code="ALIGN011",
        timestamp="2026-06-22 15:20",
        downtime_minutes=12,
        severity="Low",
        affected_lot="LOT1058",
    )
    rules = {r["rule_id"] for r in out["triggered_rules"]}
    assert "R001" not in rules
    assert "R002" not in rules
    assert "R003" not in rules
