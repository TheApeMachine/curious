from __future__ import annotations

from dataclasses import dataclass

from curious.types import RunStatus

SYSTEM_PROMPT = """You are a software engineering agent working in a local repository.

Use the provided tools to read files, edit code, and run commands. Follow the user message exactly — including workflow, git policy, and rubrics.

Rules:
- Deliver work in the working tree; the human commits later.
- Use read-only git only (status, diff, log) — never commit, add, reset, restore, switch, checkout, stash, or worktree. Curious already checked out the agent branch.
- When uncertain, read files — on-disk content is the source of truth.
- End with a clear summary of what you did and verification you ran."""


@dataclass
class HarnessResult:
    run_id: str
    status: RunStatus
    summary: str | None
    error: str | None = None
    turns: int = 0
