from __future__ import annotations

import re

from curious.review_verdict import ReviewVerdict
from curious.types import CycleRecord

WORKFLOW_BLOCKER = re.compile(
    r"\b(git commit|must commit|branch[- ]?tip|CI artifact|github actions|paste amd64|amd64\+avx|uncommitted.*HEAD|pasted amd64)\b",
    re.I,
)
META_TASK = re.compile(r"\b(run until done|continuous improvement only|meta roadmap)\b", re.I)


def assess_quality(
    *,
    fail_review: ReviewVerdict,
    task_id: str,
    cycles_to_pass: int,
    overseer_between: bool,
    same_blocker_recurred: bool,
) -> tuple[float, str | None]:
    if META_TASK.search(task_id):
        return 0.0, "meta_task"
    if fail_review.blocking_issues and all(
        WORKFLOW_BLOCKER.search(issue) for issue in fail_review.blocking_issues
    ):
        return 0.0, "workflow_only_blockers"
    if overseer_between:
        return 0.2, "overseer_intervened"
    if cycles_to_pass > 3:
        return 0.35, "noisy_trajectory"

    score = 1.0
    if cycles_to_pass == 2:
        score = 0.85
    elif cycles_to_pass == 3:
        score = 0.55
    if same_blocker_recurred:
        score *= 0.5
    return score, None


def is_recoverable_record(record: CycleRecord) -> bool:
    return record.status == "finished"


def overseer_intervened_between(
    history: list[CycleRecord], from_index: int, to_index: int
) -> bool:
    for index in range(from_index + 1, to_index):
        record = history[index]
        if record.phase != "overseer" or record.status != "finished":
            continue
        summary = record.summary or ""
        if re.search(r"steering_updated:\s*yes", summary, re.I):
            return True
        if re.search(r"OVERALL:\s*(DRIFT|BACKTRACKED)", summary, re.I):
            return True
        if re.search(r"spec_adjustments:\s*\n-\s*(?!none)", summary, re.I):
            return True
    return False


def normalize_blocker(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()
