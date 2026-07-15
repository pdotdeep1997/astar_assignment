"""Test doubles.

Principle: Dependency Injection pays off here — because the agent depends on the
LLMClient *interface*, we can drop in a fully deterministic fake with no network
and no API keys, and still exercise the real tools, real SQLite and real Chroma.
"""
from __future__ import annotations

from typing import Any

from app.llm.interfaces import LLMClient, LLMResponse, ToolCall


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


def assistant_with_calls(calls: list[ToolCall]) -> dict[str, Any]:
    """Build an OpenAI-format assistant message carrying tool calls."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": "{}"},
            }
            for c in calls
        ],
    }


class FakeLLMClient(LLMClient):
    """Returns a pre-scripted sequence of responses, ignoring the prompt.

    Each call to `complete` pops the next scripted LLMResponse. This lets a test
    describe exactly which tools the 'model' decides to call and what final
    report it submits.
    """

    def __init__(self, script: list[LLMResponse]) -> None:
        self._script = list(script)
        self.calls = 0

    def complete(self, messages, tools) -> LLMResponse:
        self.calls += 1
        if not self._script:
            raise AssertionError("FakeLLMClient ran out of scripted responses")
        return self._script.pop(0)
