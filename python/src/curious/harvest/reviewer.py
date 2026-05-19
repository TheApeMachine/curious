from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from curious.review_feedback import is_review_fail
from curious.review_verdict import parse_review_verdict
from curious.types import CuriousState

DownstreamOutcome = Literal["clean", "downstream_failed", "rolled_back"]


@dataclass
class ReviewerExample:
    diff_at_review: str
    review_verdict: dict[str, Any]
    downstream_outcome: DownstreamOutcome
    cycles_until_outcome: int
    metadata: dict[str, Any]


def _git_diff(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout or ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _files_in_diff(diff: str) -> set[str]:
    files: set[str] = set()
    for line in diff.splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            files.add(m.group(1))
    return files


def harvest_reviewer_examples(
    state: CuriousState,
    *,
    project_root: str,
) -> list[ReviewerExample]:
    examples: list[ReviewerExample] = []
    history = state.history

    for i, record in enumerate(history):
        if record.phase != "review" or record.status != "finished":
            continue
        verdict = parse_review_verdict(record.summary)
        if not verdict:
            continue

        diff = _git_diff(project_root)
        touched = _files_in_diff(diff)
        outcome: DownstreamOutcome = "clean"
        cycles_until = 0

        if verdict.overall == "PASS":
            for j in range(i + 1, len(history)):
                later = history[j]
                if later.phase != "review" or later.status != "finished":
                    continue
                if not is_review_fail(later.summary):
                    continue
                fail_verdict = parse_review_verdict(later.summary)
                if not fail_verdict:
                    break
                cycles_until = later.cycle - record.cycle
                for issue in fail_verdict.blocking_issues:
                    for f in touched:
                        if f in issue:
                            outcome = "downstream_failed"
                            break
                    if outcome == "downstream_failed":
                        break
                break

        examples.append(
            ReviewerExample(
                diff_at_review=diff[:12000],
                review_verdict={
                    "overall": verdict.overall,
                    "criteria": verdict.criteria,
                    "blocking_issues": verdict.blocking_issues,
                },
                downstream_outcome=outcome,
                cycles_until_outcome=cycles_until,
                metadata={"cycle": record.cycle},
            )
        )

    return examples


def examples_to_jsonl_rows(examples: list[ReviewerExample]) -> list[dict]:
    return [asdict(e) for e in examples]
