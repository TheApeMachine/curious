from curious.harness.providers.openai_compat import _parse_tool_calls


def test_parse_tool_calls():
    message = {
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "foo.py"}',
                },
            }
        ],
    }
    calls = _parse_tool_calls(message)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == '{"path": "foo.py"}'
