from __future__ import annotations

from typing import Any

from curious.harness.providers.types import ChatCompletion, ToolCall
from curious.types import LlmConfig


class LiteLLMProvider:
    """Optional cloud/multi-provider routing via LiteLLM (`pip install curious-py[litellm]`)."""

    def __init__(self, llm: LlmConfig) -> None:
        try:
            import litellm  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "LiteLLM provider selected but litellm is not installed. "
                "Run: pip install 'curious-py[litellm]'"
            ) from exc
        self.llm = llm

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        import litellm

        kwargs: dict[str, Any] = {
            "model": self.llm.model,
            "messages": messages,
            "tools": tools or None,
            "max_tokens": self.llm.max_tokens,
            "temperature": self.llm.temperature,
            "timeout": self.llm.timeout_sec,
        }
        if self.llm.api_key:
            kwargs["api_key"] = self.llm.api_key
        if self.llm.base_url:
            kwargs["api_base"] = self.llm.base_url

        response = litellm.completion(**kwargs)
        message = response.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in getattr(message, "tool_calls", None) or []:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "{}",
                )
            )
        return ChatCompletion(
            content=message.content or "",
            tool_calls=tool_calls,
        )
