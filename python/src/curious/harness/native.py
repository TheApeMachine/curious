from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from curious.harness.result import HarnessResult, SYSTEM_PROMPT
from curious.harness.providers import create_chat_provider
from curious.harness.tools import TOOL_DEFINITIONS, execute_tool
from curious.trajectory import ToolCallTrace, excerpt_tool_result, trim_trajectory
from curious.types import HarnessConfig, LlmConfig


def _missing_required_paths(required: list[Path] | None) -> list[Path]:
    if not required:
        return []
    missing: list[Path] = []
    for path in required:
        if not path.is_file():
            missing.append(path)
            continue
        if path.stat().st_size < 80:
            missing.append(path)
    return missing


def _nudge_missing_files_message(missing: list[Path], workspace: Path) -> str:
    rels = []
    for path in missing:
        try:
            rels.append(str(path.relative_to(workspace)))
        except ValueError:
            rels.append(str(path))
    joined = ", ".join(rels)
    return (
        f"Required file(s) not written yet: {joined}. "
        "Use the write_file tool to create them on disk before finishing. "
        "Do not reply with only a summary or paste the spec in chat."
    )


def run_native_harness(
    run_id: str,
    prompt: str,
    workspace: Path,
    llm: LlmConfig,
    harness: HarnessConfig,
    *,
    verbose: bool = False,
    required_paths: list[Path] | None = None,
) -> HarnessResult:
    """Tool-calling loop using a ChatProvider (openai_compat, litellm, transformers)."""
    provider = create_chat_provider(llm)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    last_content = ""
    trajectory: list[ToolCallTrace] = []

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
                trajectory=trim_trajectory(trajectory),
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
            missing = _missing_required_paths(required_paths)
            if missing and turn < harness.max_turns:
                if verbose:
                    print(f"[curious] harness: waiting for required file(s): {missing}")
                messages.append(
                    {
                        "role": "user",
                        "content": _nudge_missing_files_message(missing, workspace),
                    }
                )
                continue
            if missing:
                return HarnessResult(
                    run_id=run_id,
                    status="error",
                    summary=(completion.content or "").strip() or last_content,
                    error=(
                        "Agent finished without writing required file(s): "
                        + ", ".join(str(p) for p in missing)
                    ),
                    turns=turn,
                    trajectory=trim_trajectory(trajectory),
                )
            return HarnessResult(
                run_id=run_id,
                status="finished",
                summary=(completion.content or "").strip() or last_content,
                turns=turn,
                trajectory=trim_trajectory(trajectory),
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
            trajectory.append(
                ToolCallTrace(
                    name=tc.name,
                    arguments=fn_args,
                    result_excerpt=excerpt_tool_result(result),
                )
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
        trajectory=trim_trajectory(trajectory),
    )
