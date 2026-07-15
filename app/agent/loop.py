"""The agentic tool-calling loop (orchestration).

This class ONLY orchestrates the model<->tools conversation. It knows nothing about SQLite, Chroma, or which
LLM provider is used; it depends only on the LLMClient and ToolRegistry
abstractions (Dependency Injection).

The model finalises by calling a synthetic `submit_report` tool whose schema is
the InvestigationReport model — this gives us a validated, structured result
instead of hoping the model returns clean JSON in free text.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from app.agent.prompts import FINALISE_REMINDER, SYSTEM_PROMPT
from app.agent.report import InvestigationReport
from app.llm.interfaces import LLMClient, ToolCall
from app.tools.base import ToolRegistry

_SUBMIT_TOOL_NAME = "submit_report"


def _friendly_status(call: ToolCall) -> str:
    """Turn a tool call into a short human-readable progress line.

    Separation of concerns: the UI copy lives here, not in the frontend, so the
    stream is self-describing and any client can render it as-is.
    """
    a = call.arguments or {}
    name = call.name
    if name == "get_equipment_details":
        return f"Looking up equipment {a.get('identifier', '')}".strip()
    if name == "get_alarm_details":
        return f"Checking alarm {a.get('alarm_code', '')}".strip()
    if name == "get_similar_incidents":
        return "Searching for similar past incidents"
    if name == "get_maintenance_history":
        return f"Reviewing maintenance history for {a.get('equipment_id', '')}".strip()
    if name == "get_sensor_readings":
        return f"Inspecting sensor readings for {a.get('incident_id', '')}".strip()
    if name == "get_sop":
        return "Retrieving the troubleshooting SOP"
    if name == "check_escalation":
        return "Applying escalation rules"
    return f"Running {name}"


@dataclass
class AgentResult:
    """What an investigation run returns: the report plus a transparent trace."""

    report: InvestigationReport | None
    trace: list[dict[str, Any]] = field(default_factory=list)
    raw_text: str | None = None  # fallback text if no valid report was produced


class InvestigationAgent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_iterations: int = 8,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        # Build the submit_report tool schema once from the Pydantic model (DRY).
        self._submit_schema = {
            "type": "function",
            "function": {
                "name": _SUBMIT_TOOL_NAME,
                "description": "Submit the final structured investigation report.",
                "parameters": InvestigationReport.model_json_schema(),
            },
        }

    def stream(self, incident_text: str) -> Iterator[dict[str, Any]]:
        """Run the investigation, yielding progress events as they happen.

        Event shapes:
          {"type": "status", "phase": "...", "message": "..."}  # intermediate
          {"type": "final",  "report": <AgentResult>}           # terminal

        This is the single source of truth for the loop; investigate() below is
        just a thin consumer of it (DRY — no duplicated orchestration).
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": incident_text},
        ]
        tools = self._registry.schemas() + [self._submit_schema]
        trace: list[dict[str, Any]] = []

        yield {"type": "status", "phase": "start", "message": "Reading the incident…"}

        for i in range(self._max_iterations):
            # The LLM call is the slow part — announce it so the UI stays alive.
            yield {
                "type": "status",
                "phase": "think",
                "message": "Reading the incident…" if i == 0 else "Reviewing the evidence…",
            }
            resp = self._llm.complete(messages, tools)
            messages.append(resp.assistant_message)

            # No tool call -> nudge once toward submitting, else finish.
            if not resp.tool_calls:
                messages.append({"role": "user", "content": FINALISE_REMINDER})
                continue

            for call in resp.tool_calls:
                # --- finalisation path ---------------------------------------
                if call.name == _SUBMIT_TOOL_NAME:
                    try:
                        report = InvestigationReport.model_validate(call.arguments)
                        yield {
                            "type": "final",
                            "report": AgentResult(report=report, trace=trace),
                        }
                        return
                    except Exception as exc:  # validation failure -> ask to fix
                        self._append_tool_result(
                            messages, call.id, {"error": f"invalid report: {exc}"}
                        )
                        continue

                # --- normal tool execution -----------------------------------
                # Announce the step BEFORE running it (this is the intermediate
                # update the UI collapses as soon as the next one arrives).
                yield {
                    "type": "status",
                    "phase": "tool",
                    "tool": call.name,
                    "message": _friendly_status(call),
                }
                tool = self._registry.get(call.name)
                if tool is None:
                    result = {"error": f"unknown tool {call.name}"}
                else:
                    # Defensive: a tool bug must not crash the investigation.
                    try:
                        result = tool.run(**call.arguments)
                    except Exception as exc:
                        result = {"error": str(exc)}

                trace.append({"tool": call.name, "args": call.arguments, "result": result})
                self._append_tool_result(messages, call.id, result)

        # Ran out of iterations without a report: emit the trace + last text.
        last_text = next(
            (m.get("content") for m in reversed(messages)
             if m.get("role") == "assistant" and m.get("content")),
            None,
        )
        yield {
            "type": "final",
            "report": AgentResult(report=None, trace=trace, raw_text=last_text),
        }

    def investigate(self, incident_text: str) -> AgentResult:
        """Non-streaming convenience wrapper: drain the stream, return the result."""
        result = AgentResult(report=None, trace=[])
        for event in self.stream(incident_text):
            if event["type"] == "final":
                result = event["report"]
        return result

    @staticmethod
    def _append_tool_result(
        messages: list[dict[str, Any]], tool_call_id: str, result: dict[str, Any]
    ) -> None:
        """Append a tool result in OpenAI's required message shape."""
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(result, default=str),
            }
        )
