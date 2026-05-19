from __future__ import annotations

from typing import Protocol

from curious.harness.providers.litellm_provider import LiteLLMProvider
from curious.harness.providers.openai_compat import OpenAICompatProvider
from curious.harness.providers.transformers_provider import TransformersProvider
from curious.harness.providers.types import ChatCompletion
from curious.types import LlmConfig, LlmProvider


class ChatProvider(Protocol):
    def complete(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ChatCompletion: ...


def create_chat_provider(llm: LlmConfig) -> ChatProvider:
    provider: LlmProvider = llm.provider
    if provider == "openai_compat":
        return OpenAICompatProvider(llm)
    if provider == "litellm":
        return LiteLLMProvider(llm)
    if provider == "transformers":
        return TransformersProvider(llm)
    if provider == "smolagents":
        raise ValueError(
            "llm.provider=smolagents uses the smolagents harness, not create_chat_provider"
        )
    raise ValueError(
        f"Unknown llm.provider: {provider!r}. "
        "Use: openai_compat | litellm | transformers | smolagents"
    )
