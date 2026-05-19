from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from curious.harness.result import HarnessResult, SYSTEM_PROMPT
from curious.harness.providers import create_chat_provider
from curious.harness.tools import TOOL_DEFINITIONS, execute_tool
from curious.types import HarnessConfig, LlmConfig


def run_native_harness(
    run_id: str,
    prompt: str,
    workspace: Path,
    llm: LlmConfig,
    harness: HarnessConfig,
    *,
    verbose: bool = False,
) -> HarnessResult:
    """Tool-calling loop using a ChatProvider (openai_compat, litellm, transformers)."""
    provider = create_chat_provider(llm)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    last_content = ""

    for turn in range(1, harness.max_turns + 1):
        try:
            completion = provider.complete(messages, TOOL_DEFINITIONS)
        except Exception as exc:
            return HarnessResult(
                run_id=run_id,
                status="error",
                summary=None,
                error=str(exc),
                turns=turn,
            )

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": completion.content or "",
        }
        if completion.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in completion.tool_calls
            ]
        messages.append(assistant_msg)
        last_content = completion.content or last_content

        if not completion.tool_calls:
            return HarnessResult(
                run_id=run_id,
                status="finished",
                summary=(completion.content or "").strip() or last_content,
                turns=turn,
            )

        for tc in completion.tool_calls:
            try:
                fn_args = json.loads(tc.arguments or "{}")
            except json.JSONDecodeError:
                fn_args = {}
            if verbose:
                print(f"[curious] tool → {tc.name}")
            result = execute_tool(
                tc.name,
                fn_args,
                workspace,
                harness.command_timeout_sec,
            )
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    return HarnessResult(
        run_id=run_id,
        status="error",
        summary=last_content,
        error=f"max turns ({harness.max_turns}) exceeded",
        turns=harness.max_turns,
    )
