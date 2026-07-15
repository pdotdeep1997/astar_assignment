"""The four required end-to-end scenarios, run through the real agent loop with
a deterministic scripted LLM (no network). These verify orchestration: the loop
executes the tools the 'model' requests, feeds results back, and returns a
validated structured report.
"""
from __future__ import annotations

from app.agent.loop import InvestigationAgent
from app.llm.interfaces import LLMResponse, ToolCall
from tests.fakes import FakeLLMClient, assistant_with_calls


def _resp(calls: list[ToolCall]) -> LLMResponse:
    return LLMResponse(
        assistant_message=assistant_with_calls(calls), tool_calls=calls
    )


def _submit(report: dict) -> LLMResponse:
    call = ToolCall(id="submit", name="submit_report", arguments=report)
    return LLMResponse(assistant_message=assistant_with_calls([call]), tool_calls=[call])


def _agent(script, registry):
    return InvestigationAgent(FakeLLMClient(script), registry, max_iterations=8)


# --- Scenario 1: NORMAL incident (full information) ------------------------
def test_normal_incident(registry):
    script = [
        _resp([ToolCall("c1", "get_equipment_details", {"identifier": "EQ003"})]),
        _resp([ToolCall("c2", "get_alarm_details", {"alarm_code": "GAS012"})]),
        _resp([ToolCall("c3", "get_sop", {"alarm_code": "GAS012"})]),
        _submit(
            {
                "summary": "CVD-05 gas flow deviation investigated.",
                "equipment": "CVD-05",
                "alarm": "GAS012 (High)",
                "evidence": ["MFC actual below setpoint"],
                "probable_root_causes": ["MFC failure"],
                "recommended_actions": ["Calibrate MFC"],
                "escalation": {"required": True, "target": "Process Engineer"},
                "confidence": "High",
                "missing_information": [],
            }
        ),
    ]
    result = _agent(script, registry).investigate("CVD-05 gas flow deviation, 35 min.")
    assert result.report is not None
    assert result.report.equipment == "CVD-05"
    called = {t["tool"] for t in result.trace}
    assert {"get_equipment_details", "get_alarm_details", "get_sop"} <= called


# --- Scenario 2: MISSING information ---------------------------------------
def test_missing_information(registry):
    script = [
        _resp([ToolCall("c1", "get_equipment_details", {"identifier": "CMP-02"})]),
        _submit(
            {
                "summary": "CMP-02 pressure issue; alarm code not stated.",
                "equipment": "CMP-02",
                "alarm": None,
                "evidence": [],
                "probable_root_causes": [],
                "recommended_actions": ["Confirm the exact alarm code"],
                "escalation": {"required": False},
                "confidence": "Low",
                "missing_information": ["Exact alarm code for the pressure event"],
            }
        ),
    ]
    result = _agent(script, registry).investigate("CMP-02 pressure alarm, 18 min.")
    assert result.report is not None
    assert result.report.missing_information  # agent flagged the gap
    assert result.report.escalation.required is False


# --- Scenario 3: REPEATED incident (recurrence -> escalation) --------------
def test_repeated_incident_escalates(registry):
    script = [
        _resp([ToolCall("c1", "get_equipment_details", {"identifier": "EQ001"})]),
        _resp([ToolCall("c2", "get_similar_incidents",
                        {"description": "RF power instability etcher"})]),
        _resp([ToolCall("c3", "check_escalation", {
            "equipment_id": "EQ001", "alarm_code": "RF101",
            "timestamp": "2026-06-22 10:35", "downtime_minutes": 45,
            "severity": "High", "affected_lot": "LOT1055"})]),
        _submit(
            {
                "summary": "Recurring RF101 on Etcher-03; escalation required.",
                "equipment": "Etcher-03",
                "alarm": "RF101 (High)",
                "evidence": ["H101-H103 same alarm within 7 days"],
                "probable_root_causes": ["RF generator drift", "Loose RF cable"],
                "recommended_actions": ["Compare RF trace with golden run"],
                "escalation": {"required": True, "target": "Engineering Manager"},
                "confidence": "High",
                "missing_information": [],
            }
        ),
    ]
    result = _agent(script, registry).investigate(
        "Etcher-03 RF Power Instability, 45 min, LOT1055, twice last week."
    )
    # The deterministic escalation tool must have detected the recurrence.
    esc = next(t for t in result.trace if t["tool"] == "check_escalation")
    rule_ids = {r["rule_id"] for r in esc["result"]["triggered_rules"]}
    assert "R002" in rule_ids
    assert result.report.escalation.required is True


# --- Scenario 4: UNKNOWN alarm / equipment ---------------------------------
def test_unknown_alarm_graceful(registry):
    script = [
        _resp([ToolCall("c1", "get_equipment_details", {"identifier": "ALPHA-99"})]),
        _resp([ToolCall("c2", "get_alarm_details", {"alarm_code": "ZX999"})]),
        _submit(
            {
                "summary": "Unknown tool ALPHA-99 and alarm ZX999; cannot verify.",
                "equipment": None,
                "alarm": None,
                "evidence": [],
                "probable_root_causes": [],
                "recommended_actions": ["Confirm the correct equipment and alarm code"],
                "escalation": {"required": False},
                "confidence": "Low",
                "missing_information": ["Valid equipment id", "Valid alarm code"],
            }
        ),
    ]
    result = _agent(script, registry).investigate("Unknown tool ALPHA-99 has alarm ZX999.")
    # Tools returned not-found rather than raising.
    eq = next(t for t in result.trace if t["tool"] == "get_equipment_details")
    al = next(t for t in result.trace if t["tool"] == "get_alarm_details")
    assert eq["result"]["found"] is False
    assert al["result"]["found"] is False
    assert result.report.missing_information
