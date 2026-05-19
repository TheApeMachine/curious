from __future__ import annotations

import json
from dataclasses import dataclass, field

TOOL_RESULT_EXCERPT = 2048
TRAJECTORY_MAX_BYTES = 50 * 1024


@dataclass
class ToolCallTrace:
    name: str
    arguments: dict
    result_excerpt: str

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "resultExcerpt": self.result_excerpt,
        }

    @classmethod
    def from_json(cls, data: dict) -> ToolCallTrace:
        return cls(
            name=data["name"],
            arguments=data.get("arguments") or {},
            result_excerpt=data.get("resultExcerpt", data.get("result_excerpt", "")),
        )


def excerpt_tool_result(result: str, limit: int = TOOL_RESULT_EXCERPT) -> str:
    if len(result) <= limit:
        return result
    return result[:limit] + f"\n… ({len(result) - limit} bytes truncated)"


def trim_trajectory(traces: list[ToolCallTrace]) -> list[ToolCallTrace]:
    """Cap total serialized size; keep head and tail when over budget."""
    if not traces:
        return traces

    def size_of(items: list[ToolCallTrace]) -> int:
        return len(json.dumps([t.to_json() for t in items], ensure_ascii=False).encode())

    if size_of(traces) <= TRAJECTORY_MAX_BYTES:
        return traces

    if len(traces) <= 2:
        return traces

    head = traces[: max(1, len(traces) // 4)]
    tail = traces[-max(1, len(traces) // 4) :]
    merged = head + tail
    while len(merged) > 2 and size_of(merged) > TRAJECTORY_MAX_BYTES:
        if len(head) > len(tail):
            head = head[:-1]
        else:
            tail = tail[1:]
        merged = head + tail
    return merged


def trajectory_to_messages(traces: list[ToolCallTrace]) -> list[dict]:
    """Format tool traces as chat messages for DPO / training."""
    messages: list[dict] = []
    for i, trace in enumerate(traces):
        call_id = f"call_{i}"
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": trace.name,
                            "arguments": json.dumps(trace.arguments, ensure_ascii=False),
                        },
                    }
                ],
            }
        )
        messages.append(
            {"role": "tool", "tool_call_id": call_id, "content": trace.result_excerpt}
        )
    return messages
