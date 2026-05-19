from __future__ import annotations

import json
import re

from curious.harness.providers.types import ToolCall

# -----------------------------------------------------------------------------
# Model-specific fallbacks when `apply_chat_template(..., tools=...)` does not
# return structured tool_calls and we must parse raw generated text.
#
# Qwen3-Coder emits <tool_call>{...}</tool_call> blocks. DeepSeek, CodeLlama,
# Mistral, etc. use different markers or none at all without FC fine-tuning.
# TODO: dispatch by model family (qwen / deepseek / llama) when we support more
# than Qwen3-Coder as the default HF model.
# -----------------------------------------------------------------------------

_QWEN_TOOL_CALL_BLOCK = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


def _parse_qwen_tool_calls(text: str) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, match in enumerate(_QWEN_TOOL_CALL_BLOCK.finditer(text)):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = payload.get("name") or payload.get("function", "")
        args = payload.get("arguments", {})
        args_str = json.dumps(args) if isinstance(args, dict) else str(args)
        if name:
            calls.append(
                ToolCall(id=f"call_{index}", name=name, arguments=args_str)
            )
    return calls


def parse_tool_calls_from_text(text: str, model_id: str) -> list[ToolCall]:
    """Parse tool invocations from model output text (family-specific)."""
    model_lower = model_id.lower()
    if "qwen" in model_lower:
        return _parse_qwen_tool_calls(text)
    # Unknown families: try Qwen format (best-effort), may return [] for other templates
    return _parse_qwen_tool_calls(text)


def strip_tool_call_markup(text: str, model_id: str) -> str:
    """Remove tool-call blocks from assistant text for display content."""
    if "qwen" in model_id.lower():
        return _QWEN_TOOL_CALL_BLOCK.sub("", text).strip()
    return text.strip()
