from curious.harness.providers.tool_call_parsers import (
    parse_tool_calls_from_text,
    strip_tool_call_markup,
)


def test_qwen_tool_call_block():
    text = 'Done.\n<tool_call>{"name": "read_file", "arguments": {"path": "a.py"}}</tool_call>'
    calls = parse_tool_calls_from_text(text, "Qwen/Qwen3-Coder-30B-A3B-Instruct")
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert '"path": "a.py"' in calls[0].arguments


def test_strip_qwen_markup():
    text = 'summary\n<tool_call>{"name": "x", "arguments": {}}</tool_call>'
    assert "<tool_call>" not in strip_tool_call_markup(text, "Qwen/Qwen3-Coder-30B-A3B-Instruct")
