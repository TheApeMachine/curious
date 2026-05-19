from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from dataclasses import replace

from curious.harness.agent import run_harness
from curious.harness.result import HarnessResult
from curious.types import BestOfNConfig, HarnessConfig, LlmConfig
from curious.verifier.model import VerifierModel


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _worktree_base(project_root: Path, cycle: int) -> Path:
    return project_root / ".curious" / "best-of-n" / f"{cycle:04d}"


def _create_worktree(main_root: Path, cycle: int, index: int, branch: str) -> Path:
    base = _worktree_base(main_root, cycle)
    base.mkdir(parents=True, exist_ok=True)
    wt_path = base / str(index)
    if wt_path.exists():
        _git(main_root, "worktree", "remove", "--force", str(wt_path))
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    result = _git(main_root, "worktree", "add", "-B", branch, str(wt_path), "HEAD")
    if result.returncode != 0:
        raise RuntimeError(f"worktree add failed: {result.stderr}")
    return wt_path


def _remove_worktrees(main_root: Path, cycle: int) -> None:
    base = _worktree_base(main_root, cycle)
    if not base.is_dir():
        return
    for child in base.iterdir():
        if child.is_dir():
            _git(main_root, "worktree", "remove", "--force", str(child))
    shutil.rmtree(base, ignore_errors=True)


def _diff_in_worktree(wt: Path) -> str:
    r = _git(wt, "diff", "HEAD")
    return r.stdout or ""


def _apply_winner_to_main(main_root: Path, winner_wt: Path) -> None:
    """Copy winner tree changes onto main worktree via checkout of files."""
    r = _git(winner_wt, "diff", "--name-only", "HEAD")
    files = [f for f in (r.stdout or "").splitlines() if f.strip()]
    for rel in files:
        src = winner_wt / rel
        dest = main_root / rel
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def develop_best_of_n(
    prompt: str,
    workspace: Path,
    llm: LlmConfig,
    harness: HarnessConfig,
    verifier: VerifierModel,
    *,
    cycle: int,
    spec_section: str,
    agents_section: str,
    verbose: bool = False,
    bon: BestOfNConfig | None = None,
) -> HarnessResult:
    """Run N develop trajectories in git worktrees; pick highest verifier score."""
    cfg = bon or harness.best_of_n
    n = max(1, cfg.n)
    temps = cfg.temperatures[:n]
    while len(temps) < n:
        temps.append(temps[-1] if temps else 0.2)

    main_root = workspace
    if _git(main_root, "rev-parse", "--git-dir").returncode != 0:
        return run_harness(prompt, workspace, llm, harness, verbose=verbose)

    candidates: list[tuple[float, HarnessResult, Path]] = []

    try:
        for i in range(n):
            branch = f"curious-bon-{cycle}-{i}"
            wt = _create_worktree(main_root, cycle, i, branch)
            temp_llm = replace(llm, temperature=temps[i])
            result = run_harness(
                prompt,
                wt,
                temp_llm,
                harness,
                verbose=verbose,
            )
            diff = _diff_in_worktree(wt)
            scores = verifier.score(
                diff=diff,
                spec_section=spec_section,
                agents_section=agents_section,
            )
            candidates.append((scores.overall, result, wt))
            print(
                f"[curious] best-of-n candidate {i + 1}/{n}: "
                f"verifier={scores.overall:.3f} status={result.status}"
            )

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_result, best_wt = candidates[0]
        print(f"[curious] best-of-n winner: verifier={best_score:.3f}")
        _apply_winner_to_main(main_root, best_wt)
        return best_result
    finally:
        _remove_worktrees(main_root, cycle)
