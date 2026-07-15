"""Tool abstraction and registry.

Principle: Command pattern + Liskov Substitution — every tool is a `Tool`
with the same shape (name / description / JSON-schema parameters / run()), so
the agent loop can treat them uniformly and any tool is substitutable.

Principle: Dependency Injection — tools receive their data-store dependencies
through their constructors, never reaching for globals. This is what makes the
backing stores swappable and the tools unit-testable with fakes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Base class for every agent-callable tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema shown to the LLM

    @abstractmethod
    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool. Must return a JSON-serialisable dict.

        Contract: tools NEVER raise on 'not found'. They return a structured
        result (e.g. {"found": false, ...}) so the agent can reason about
        missing data — this is what handles the 'unknown alarm' scenario
        gracefully (defensive programming)."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Serialise to the OpenAI/LiteLLM 'tools' function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Holds tools by name and exposes them to the agent loop.

    Principle: Open/Closed — register new tools without modifying the loop.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)
