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
from dataclasses import dataclass, field
from typing import Any

from app.agent.prompts import FINALISE_REMINDER, SYSTEM_PROMPT
from app.agent.report import InvestigationReport
from app.llm.interfaces import LLMClient
from app.tools.base import ToolRegistry

_SUBMIT_TOOL_NAME = "submit_report"


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

    def investigate(self, incident_text: str) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": incident_text},
        ]
        tools = self._registry.schemas() + [self._submit_schema]
        trace: list[dict[str, Any]] = []

        for _ in range(self._max_iterations):
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
                        return AgentResult(report=report, trace=trace)
                    except Exception as exc:  # validation failure -> ask to fix
                        self._append_tool_result(
                            messages, call.id, {"error": f"invalid report: {exc}"}
                        )
                        continue

                # --- normal tool execution -----------------------------------
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

        # Ran out of iterations without a report: return the trace + last text.
        last_text = next(
            (m.get("content") for m in reversed(messages)
             if m.get("role") == "assistant" and m.get("content")),
            None,
        )
        return AgentResult(report=None, trace=trace, raw_text=last_text)

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
