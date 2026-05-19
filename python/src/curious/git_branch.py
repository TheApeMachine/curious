from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_AGENT_BRANCH = "curious"


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def git_toplevel(start: Path) -> Path | None:
    result = _run_git(start, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def is_git_repo(start: Path) -> bool:
    return git_toplevel(start) is not None


def current_branch(repo_root: Path) -> str | None:
    result = _run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def branch_exists(repo_root: Path, name: str) -> bool:
    result = _run_git(
        repo_root,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{name}",
    )
    return result.returncode == 0


def ensure_agent_branch(
    project_root: Path,
    branch: str = DEFAULT_AGENT_BRANCH,
    *,
    enabled: bool = True,
) -> str | None:
    """Switch the repo to the Curious agent branch. Returns branch name or None if skipped."""
    if not enabled:
        return None

    root = git_toplevel(Path(project_root))
    if root is None:
        print("[curious] git: not a repository — skipping agent branch switch")
        return None

    current = current_branch(root)
    if current == branch:
        print(f"[curious] git: already on branch {branch}")
        return branch

    if branch_exists(root, branch):
        result = _run_git(root, "switch", branch)
        if result.returncode != 0:
            result = _run_git(root, "checkout", branch)
    else:
        result = _run_git(root, "switch", "-c", branch)
        if result.returncode != 0:
            result = _run_git(root, "checkout", "-b", branch)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Failed to switch to branch {branch!r}"
            + (f" (from {current})" if current else "")
            + (f": {detail}" if detail else "")
        )

    print(
        f"[curious] git: switched to branch {branch}"
        + (f" (from {current})" if current else "")
    )
    return branch


def agent_branch_prompt_note(branch: str) -> str:
    return (
        f"\n**Branch:** Curious switched this repo to `{branch}` before this run. "
        "Stay on this branch; do not run `git switch`, `git checkout`, or worktrees.\n"
    )
