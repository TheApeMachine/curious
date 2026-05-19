from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from curious.git_branch import (
    current_branch,
    ensure_agent_branch,
    git_toplevel,
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_ensure_creates_and_switches(git_repo: Path) -> None:
    assert current_branch(git_repo) == "main" or current_branch(git_repo) == "master"
    branch = ensure_agent_branch(git_repo, "curious")
    assert branch == "curious"
    assert current_branch(git_repo) == "curious"


def test_ensure_idempotent_on_curious(git_repo: Path) -> None:
    ensure_agent_branch(git_repo, "curious")
    ensure_agent_branch(git_repo, "curious")
    assert current_branch(git_repo) == "curious"


def test_ensure_switches_back_from_other(git_repo: Path) -> None:
    ensure_agent_branch(git_repo, "curious")
    _git(git_repo, "switch", "-c", "feature-x")
    assert current_branch(git_repo) == "feature-x"
    ensure_agent_branch(git_repo, "curious")
    assert current_branch(git_repo) == "curious"


def test_disabled_skips(git_repo: Path) -> None:
    before = current_branch(git_repo)
    assert ensure_agent_branch(git_repo, "curious", enabled=False) is None
    assert current_branch(git_repo) == before


def test_not_git_repo(tmp_path: Path) -> None:
    assert git_toplevel(tmp_path) is None
    assert ensure_agent_branch(tmp_path, "curious") is None
