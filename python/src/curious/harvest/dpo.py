from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from curious.harvest.git_join import git_commit_before, git_diff_between, is_git_repository
from curious.harvest.quality import (
    assess_quality,
    is_recoverable_record,
    normalize_blocker,
    overseer_intervened_between,
)
from curious.review_feedback import is_review_fail
from curious.review_verdict import extract_task_id, parse_review_verdict
from curious.trajectory import ToolCallTrace, trajectory_to_messages
from curious.types import CuriousState, CycleRecord


@dataclass
class DpoExample:
    format: str
    task_id: str
    prompt: str
    chosen: str
    rejected: str
    rationale: list[str]
    quality_score: float
    metadata: dict[str, Any]
    reject_reason: str | None = None
    chosen_trajectory: list[ToolCallTrace] | None = None
    rejected_trajectory: list[ToolCallTrace] | None = None


def _trajectory_text(traces: list[ToolCallTrace] | None, summary: str) -> str:
    if not traces:
        return summary
    import json

    msgs = trajectory_to_messages(traces)
    return json.dumps({"messages": msgs, "summary": summary}, ensure_ascii=False)


def _find_develop_before_review(
    history: list[CycleRecord], review_index: int
) -> tuple[int, CycleRecord] | None:
    review = history[review_index]
    for index in range(review_index - 1, -1, -1):
        record = history[index]
        if record.phase == "develop" and record.cycle == review.cycle:
            return index, record
        if record.phase in ("review", "sync"):
            break
    for index in range(review_index - 1, -1, -1):
        record = history[index]
        if record.phase == "develop":
            return index, record
    return None


def _build_prompt(
    *,
    task_id: str,
    spec_path: str,
    fail_review,
    fail_develop: CycleRecord,
    history_before: list[CycleRecord],
) -> str:
    history_tail = "\n".join(
        f"- cycle {r.cycle} {r.phase} ({r.status}): "
        f"{(r.summary or '')[:200].replace(chr(10), ' ')}"
        for r in history_before[-6:]
    ) or "(none)"
    return "\n".join(
        [
            f"# Develop task {task_id}",
            "",
            f"Spec: {spec_path}",
            "",
            "## Prior orchestrator context",
            history_tail,
            "",
            "## Review feedback (FAIL)",
            "blocking_issues:",
            *[f"- {i}" for i in fail_review.blocking_issues],
            "",
            "evidence:",
            *[f"- {e}" for e in fail_review.evidence],
            "",
            "## Previous develop summary",
            (fail_develop.summary or "").strip() or "(no summary)",
        ]
    )


def _find_pass_review_for_task(
    history: list[CycleRecord], after_index: int, task_id: str
) -> tuple[int, CycleRecord] | None:
    fail_cycle = history[after_index].cycle
    for index in range(after_index + 1, len(history)):
        record = history[index]
        if record.phase != "review" or not is_recoverable_record(record):
            continue
        if is_review_fail(record.summary):
            continue
        verdict = parse_review_verdict(record.summary)
        if not verdict or verdict.overall != "PASS":
            continue
        pass_develop = _find_develop_before_review(history, index)
        if not pass_develop:
            continue
        _, develop_record = pass_develop
        develop_mentions = (
            extract_task_id(develop_record.summary) == task_id
            or (task_id in (develop_record.summary or ""))
        )
        if not develop_mentions and develop_record.cycle > fail_cycle + 2:
            continue
        return index, record
    return None


def harvest_dpo_pairs(
    state: CuriousState,
    *,
    project_root: str,
    cwd: str,
    spec_path: str,
    min_quality: float,
    include_rejected: bool,
) -> list[DpoExample]:
    history = state.history
    examples: list[DpoExample] = []
    has_git = is_git_repository(cwd)

    for review_index, review_record in enumerate(history):
        if (
            review_record.phase != "review"
            or not is_recoverable_record(review_record)
            or not is_review_fail(review_record.summary)
        ):
            continue

        fail_verdict = parse_review_verdict(review_record.summary)
        if not fail_verdict:
            continue

        task_id = extract_task_id(fail_verdict.next_develop) or extract_task_id(
            review_record.summary
        )
        if not task_id:
            continue

        fail_develop = _find_develop_before_review(history, review_index)
        if not fail_develop or not (fail_develop[1].summary or "").strip():
            continue
        fail_dev_index, fail_dev_record = fail_develop

        pass_match = _find_pass_review_for_task(history, review_index, task_id)
        if not pass_match:
            continue
        pass_review_index, pass_review_record = pass_match

        pass_develop = _find_develop_before_review(history, pass_review_index)
        if not pass_develop or not (pass_develop[1].summary or "").strip():
            continue
        _, pass_dev_record = pass_develop

        cycles_to_pass = pass_review_record.cycle - review_record.cycle
        blocker_key = "|".join(
            normalize_blocker(i) for i in fail_verdict.blocking_issues
        )
        same_blocker_recurred = False
        for record in history[review_index + 1 : pass_review_index]:
            if record.phase != "review" or not is_review_fail(record.summary):
                continue
            verdict = parse_review_verdict(record.summary)
            if not verdict:
                continue
            key = "|".join(normalize_blocker(i) for i in verdict.blocking_issues)
            if key == blocker_key and key:
                same_blocker_recurred = True
                break

        overseer_between = overseer_intervened_between(
            history, review_index, pass_review_index
        )
        score, reject_reason = assess_quality(
            fail_review=fail_verdict,
            task_id=task_id,
            cycles_to_pass=cycles_to_pass,
            overseer_between=overseer_between,
            same_blocker_recurred=same_blocker_recurred,
        )

        if score < min_quality and not include_rejected:
            continue

        prompt = _build_prompt(
            task_id=task_id,
            spec_path=spec_path,
            fail_review=fail_verdict,
            fail_develop=fail_dev_record,
            history_before=history[:review_index],
        )

        git_meta: dict[str, Any] = {}
        if has_git:
            rejected_sha = git_commit_before(cwd, fail_dev_record.finished_at)
            chosen_sha = git_commit_before(cwd, pass_dev_record.finished_at)
            if rejected_sha:
                git_meta["rejected_sha"] = rejected_sha
            if chosen_sha:
                git_meta["chosen_sha"] = chosen_sha
            if rejected_sha and chosen_sha:
                diff = git_diff_between(cwd, rejected_sha, chosen_sha)
                if diff is not None:
                    git_meta["diff"] = diff

        criteria_fail = [
            k for k, v in fail_verdict.criteria.items() if v == "FAIL"
        ]

        examples.append(
            DpoExample(
                format="dpo",
                task_id=task_id,
                prompt=prompt,
                chosen=_trajectory_text(
                    pass_dev_record.trajectory,
                    pass_dev_record.summary.strip(),
                ),
                rejected=_trajectory_text(
                    fail_dev_record.trajectory,
                    fail_dev_record.summary.strip(),
                ),
                chosen_trajectory=pass_dev_record.trajectory or None,
                rejected_trajectory=fail_dev_record.trajectory or None,
                rationale=fail_verdict.blocking_issues,
                quality_score=score,
                reject_reason=reject_reason,
                metadata={
                    "fail_cycle": review_record.cycle,
                    "pass_cycle": pass_review_record.cycle,
                    "fail_develop_run_id": fail_dev_record.run_id,
                    "pass_develop_run_id": pass_dev_record.run_id,
                    "fail_review_run_id": review_record.run_id,
                    "pass_review_run_id": pass_review_record.run_id,
                    "cycles_to_pass": cycles_to_pass,
                    "git": git_meta or None,
                    "criteria_fail": criteria_fail or None,
                },
            )
        )

    return examples
