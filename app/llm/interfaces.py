"""LLM client abstraction.

Principle: Dependency Inversion — the agent depends on this `LLMClient`
interface, NOT on LiteLLM or any vendor SDK. That is exactly what lets us:
  * swap OpenAI <-> Anthropic <-> local models, and
  * inject a deterministic FakeLLMClient in tests (no network, no keys).

Canonical message format: we use OpenAI's chat-message schema as the lingua
franca. LiteLLM translates it per-provider, so this choice stays neutral.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalised model reply.

    `assistant_message` is the raw OpenAI-format message dict, appended verbatim
    to the running conversation so tool-call bookkeeping stays consistent.
    """

    assistant_message: dict[str, Any]
    tool_calls: list[ToolCall] = field(default_factory=list)
    content: str | None = None


class LLMClient(ABC):
    @abstractmethod
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        """One round-trip: given the conversation and available tools, return
        the model's reply (which may request tool calls)."""
