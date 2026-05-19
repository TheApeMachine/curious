from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from curious.harness.providers.types import ChatCompletion, ToolCall
from curious.types import LlmConfig

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LOCAL_API_KEY = "local"


def _chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _parse_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for item in message.get("tool_calls") or []:
        fn = item.get("function") or {}
        calls.append(
            ToolCall(
                id=item.get("id") or f"call_{len(calls)}",
                name=fn.get("name", ""),
                arguments=fn.get("arguments") or "{}",
            )
        )
    return calls


class OpenAICompatProvider:
    """Talk to any OpenAI-compatible HTTP API (Ollama, vLLM, llama.cpp, etc.). Stdlib only."""

    def __init__(self, llm: LlmConfig) -> None:
        self.llm = llm
        self.base_url = (llm.base_url or DEFAULT_LOCAL_BASE_URL).rstrip("/")
        self.api_key = llm.api_key or DEFAULT_LOCAL_API_KEY

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        body: dict[str, Any] = {
            "model": self.llm.model,
            "messages": messages,
            "max_tokens": self.llm.max_tokens,
            "temperature": self.llm.temperature,
        }
        if tools:
            body["tools"] = tools

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            _chat_url(self.base_url),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.llm.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM HTTP {exc.code} from {self.base_url}: {detail[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach LLM at {self.base_url} — is Ollama/vLLM running? ({exc.reason})"
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM returned no choices: {json.dumps(data)[:300]}")

        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        return ChatCompletion(
            content=content,
            tool_calls=_parse_tool_calls(message),
            raw=data,
        )
