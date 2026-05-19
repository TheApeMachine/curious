from __future__ import annotations

import json
from typing import Any

from curious.trajectory import ToolCallTrace, trajectory_to_messages


def completion_from_row(row: dict, tokenizer: Any | None = None) -> str:
    """Prefer serialized trajectory+summary; fall back to plain chosen/rejected."""
    chosen_traj = row.get("chosen_trajectory")
    if chosen_traj:
        traces = [
            ToolCallTrace(
                name=t["name"],
                arguments=t.get("arguments") or {},
                result_excerpt=t.get("resultExcerpt", t.get("result_excerpt", "")),
            )
            for t in chosen_traj
        ]
        summary = ""
        raw = row.get("chosen", "")
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                summary = parsed.get("summary", "")
            except json.JSONDecodeError:
                summary = raw
        else:
            summary = raw
        return format_trajectory_completion(traces, summary, tokenizer=tokenizer)
    return row.get("chosen", "")


def rejection_from_row(row: dict, tokenizer: Any | None = None) -> str:
    rejected_traj = row.get("rejected_trajectory")
    if rejected_traj:
        traces = [
            ToolCallTrace(
                name=t["name"],
                arguments=t.get("arguments") or {},
                result_excerpt=t.get("resultExcerpt", t.get("result_excerpt", "")),
            )
            for t in rejected_traj
        ]
        summary = ""
        raw = row.get("rejected", "")
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                summary = parsed.get("summary", "")
            except json.JSONDecodeError:
                summary = raw
        else:
            summary = raw
        return format_trajectory_completion(traces, summary, tokenizer=tokenizer)
    return row.get("rejected", "")


def format_trajectory_completion(
    traces: list[ToolCallTrace],
    summary: str,
    *,
    tokenizer: Any | None,
) -> str:
    """Format tool trajectory + summary for DPO/GRPO (chat template when tokenizer given)."""
    messages = trajectory_to_messages(traces)
    if summary.strip():
        messages.append({"role": "assistant", "content": summary.strip()})

    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        except Exception:
            pass

    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                parts.append(
                    f"<tool_call>{fn.get('name', '')}({fn.get('arguments', '')})</tool_call>"
                )
        elif content:
            parts.append(f"<{role}>\n{content}\n</{role}>")
    return "\n".join(parts)
