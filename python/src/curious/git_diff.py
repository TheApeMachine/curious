from __future__ import annotations

import subprocess
from pathlib import Path

DIFF_AT_REVIEW_MAX_CHARS = 12_000


def git_diff_at_head(project_root: str | Path, cwd: str | None = None) -> str:
    """Unified diff of working tree vs HEAD (same view the reviewer sees)."""
    root = Path(project_root)
    work = Path(cwd) if cwd else root
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout or ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def capture_diff_at_review(project_root: str | Path, cwd: str | None = None) -> str | None:
    diff = git_diff_at_head(project_root, cwd).strip()
    if not diff:
        return None
    if len(diff) > DIFF_AT_REVIEW_MAX_CHARS:
        return diff[:DIFF_AT_REVIEW_MAX_CHARS]
    return diff
