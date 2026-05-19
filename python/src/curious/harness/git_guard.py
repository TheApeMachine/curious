from __future__ import annotations

import re

# Block mutating git subcommands in shell tool invocations.
FORBIDDEN_GIT = re.compile(
    r"\bgit\s+("
    r"add|commit|reset|restore|checkout|switch|clean|stash|revert|rebase|"
    r"cherry-pick|merge|pull|push|am|worktree"
    r")\b",
    re.I,
)


def is_forbidden_git_command(command: str) -> bool:
    return bool(FORBIDDEN_GIT.search(command))
