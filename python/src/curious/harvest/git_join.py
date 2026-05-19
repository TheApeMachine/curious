from __future__ import annotations

import subprocess
from pathlib import Path


def is_git_repository(cwd: str | Path) -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=cwd,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def git_commit_before(cwd: str | Path, iso_time: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-list", "-1", f"--before={iso_time}", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        sha = result.stdout.strip()
        return sha if sha else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_diff_between(cwd: str | Path, from_sha: str, to_sha: str) -> str | None:
    if from_sha == to_sha:
        return ""
    try:
        result = subprocess.run(
            ["git", "diff", f"{from_sha}..{to_sha}"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
