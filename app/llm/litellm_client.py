"""LiteLLM-backed LLMClient.

Principle: Adapter — wraps LiteLLM's `completion()` and adapts its response to
our neutral LLMResponse. LiteLLM speaks OpenAI's function-calling format for
every provider, so this single adapter serves OpenAI, Anthropic and local
models; the caller only ever changes the model string in config.
"""
from __future__ import annotations

import json
from typing import Any

from app.llm.interfaces import LLMClient, LLMResponse, ToolCall


class LiteLLMClient(LLMClient):
    def __init__(
        self, model: str, api_key: str | None = None, api_base: str | None = None
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        from litellm import completion

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        # Only pass credentials when provided (local models need none).
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._api_base:
            kwargs["api_base"] = self._api_base

        resp = completion(**kwargs)
        msg = resp.choices[0].message

        # Parse tool calls into our neutral representation.
        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )

        # `model_dump` gives the OpenAI-format dict we append back to messages.
        assistant_message = msg.model_dump()
        return LLMResponse(
            assistant_message=assistant_message,
            tool_calls=tool_calls,
            content=msg.content,
        )
