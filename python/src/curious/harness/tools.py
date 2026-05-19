from __future__ import annotations

import json
import subprocess
from pathlib import Path

from curious.harness.git_guard import is_forbidden_git_command

MAX_TOOL_OUTPUT = 48_000

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the project workspace. "
                "Use for tests, builds, git status/diff/log (read-only git only). "
                "Never run git commit, add, reset, restore, checkout, stash, or worktree."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file (optionally slice by line range).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {
                        "type": "integer",
                        "description": "1-based start line (default 1)",
                    },
                    "limit": {"type": "integer", "description": "Max lines to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a UTF-8 text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_replace",
            "description": "Replace one exact string in a file (must be unique).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
]


def _truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT:
        return text
    return text[: MAX_TOOL_OUTPUT - 80] + "\n…(output truncated)…"


def _resolve_path(workspace: Path, rel: str) -> Path:
    target = (workspace / rel).resolve()
    workspace_resolved = workspace.resolve()
    if not str(target).startswith(str(workspace_resolved)):
        raise ValueError(f"path escapes workspace: {rel}")
    return target


def execute_tool(
    name: str,
    arguments: dict,
    workspace: Path,
    timeout_sec: int,
) -> str:
    if name == "run_command":
        return _run_command(workspace, arguments, timeout_sec)
    if name == "read_file":
        return _read_file(workspace, arguments)
    if name == "write_file":
        return _write_file(workspace, arguments)
    if name == "search_replace":
        return _search_replace(workspace, arguments)
    return json.dumps({"error": f"unknown tool: {name}"})


def _run_command(workspace: Path, args: dict, timeout_sec: int) -> str:
    command = args.get("command", "").strip()
    if not command:
        return json.dumps({"error": "empty command"})
    if is_forbidden_git_command(command):
        return json.dumps(
            {
                "error": "forbidden: mutating git commands are not allowed (human commits only)",
                "command": command,
            }
        )
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return _truncate(
            json.dumps(
                {
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                },
                ensure_ascii=False,
            )
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"command timed out after {timeout_sec}s"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _read_file(workspace: Path, args: dict) -> str:
    try:
        path = _resolve_path(workspace, args["path"])
        if not path.is_file():
            return json.dumps({"error": f"not found: {args['path']}"})
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        offset = max(1, int(args.get("offset", 1)))
        limit = args.get("limit")
        start = offset - 1
        if limit is not None:
            end = start + int(limit)
            slice_lines = lines[start:end]
        else:
            slice_lines = lines[start:]
        numbered = [
            f"{offset + i:6d}|{line}" for i, line in enumerate(slice_lines)
        ]
        return _truncate("\n".join(numbered) if numbered else "(empty)")
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _write_file(workspace: Path, args: dict) -> str:
    try:
        path = _resolve_path(workspace, args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.get("content", ""), encoding="utf-8")
        return json.dumps({"ok": True, "path": str(path.relative_to(workspace))})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _search_replace(workspace: Path, args: dict) -> str:
    try:
        path = _resolve_path(workspace, args["path"])
        if not path.is_file():
            return json.dumps({"error": f"not found: {args['path']}"})
        content = path.read_text(encoding="utf-8")
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        count = content.count(old)
        if count == 0:
            return json.dumps({"error": "old_string not found"})
        if count > 1:
            return json.dumps({"error": f"old_string matched {count} times — must be unique"})
        path.write_text(content.replace(old, new, 1), encoding="utf-8")
        return json.dumps({"ok": True, "replacements": 1})
    except Exception as exc:
        return json.dumps({"error": str(exc)})
