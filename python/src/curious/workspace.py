from __future__ import annotations

from pathlib import Path

from curious.git_branch import agent_branch_prompt_note, current_branch, ensure_agent_branch, git_toplevel
from curious.types import ResolvedConfig


def prepare_agent_workspace(config: ResolvedConfig) -> str | None:
    """Ensure the repo is on the Curious agent branch before any harness run."""
    return ensure_agent_branch(
        Path(config.project_root),
        config.agent_branch,
        enabled=config.ensure_agent_branch,
    )


def agent_branch_prompt_note_for_config(config: ResolvedConfig) -> str:
    if not config.ensure_agent_branch:
        return ""
    root = git_toplevel(Path(config.project_root))
    if root is None:
        return ""
    branch = current_branch(root) or config.agent_branch
    return agent_branch_prompt_note(branch)
