from __future__ import annotations

from pathlib import Path

from curious.harness.tools import execute_tool


def build_smolagents_tools(workspace: Path, command_timeout_sec: int) -> list:
    """Curious tools as [smolagents](https://huggingface.co/docs/smolagents/index) Tool objects."""
    try:
        from smolagents import Tool
    except ImportError as exc:
        raise ImportError(
            "llm.provider=smolagents requires: pip install 'curious-py[smolagents]'"
        ) from exc

    ws = workspace.resolve()
    timeout = command_timeout_sec

    class RunCommandTool(Tool):
        name = "run_command"
        description = (
            "Run a shell command in the project workspace. Read-only git only — "
            "never git commit, add, reset, restore, checkout, stash, or worktree."
        )
        inputs = {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            }
        }
        output_type = "string"

        def forward(self, command: str) -> str:
            return execute_tool(
                "run_command",
                {"command": command},
                ws,
                timeout,
            )

    class ReadFileTool(Tool):
        name = "read_file"
        description = "Read a UTF-8 text file (optional 1-based line offset and limit)."
        inputs = {
            "path": {"type": "string", "description": "Path relative to workspace"},
            "offset": {
                "type": "integer",
                "description": "1-based start line",
                "nullable": True,
            },
            "limit": {
                "type": "integer",
                "description": "Max lines",
                "nullable": True,
            },
        }
        output_type = "string"

        def forward(self, path: str, offset: int | None = None, limit: int | None = None) -> str:
            args: dict = {"path": path}
            if offset is not None:
                args["offset"] = offset
            if limit is not None:
                args["limit"] = limit
            return execute_tool("read_file", args, ws, timeout)

    class WriteFileTool(Tool):
        name = "write_file"
        description = "Create or overwrite a UTF-8 text file."
        inputs = {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }
        output_type = "string"

        def forward(self, path: str, content: str) -> str:
            return execute_tool("write_file", {"path": path, "content": content}, ws, timeout)

    class SearchReplaceTool(Tool):
        name = "search_replace"
        description = "Replace one exact unique string in a file."
        inputs = {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        }
        output_type = "string"

        def forward(self, path: str, old_string: str, new_string: str) -> str:
            return execute_tool(
                "search_replace",
                {
                    "path": path,
                    "old_string": old_string,
                    "new_string": new_string,
                },
                ws,
                timeout,
            )

    return [RunCommandTool(), ReadFileTool(), WriteFileTool(), SearchReplaceTool()]
