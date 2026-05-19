from __future__ import annotations

import json
from typing import Any


def format_tools_for_text_prompt(tools: list[dict[str, Any]]) -> str:
    """Fallback when the tokenizer chat template does not accept `tools=`."""
    lines = [
        "",
        "## Tools",
        "Invoke tools with Qwen-style blocks (one per call):",
        '<tool_call>{"name": "<tool>", "arguments": {<json>}}</tool_call>',
        "",
    ]
    for tool in tools:
        fn = tool.get("function") or {}
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        lines.append(f"- **{name}**: {desc}")
        lines.append(f"  parameters: {json.dumps(params, ensure_ascii=False)}")
    return "\n".join(lines)
