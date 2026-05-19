from __future__ import annotations

import re

from curious.review_feedback import is_review_fail
from curious.types import CuriousConfig, CuriousState, CycleRecord

HISTORY_LIMIT = 40


def should_run_overseer(state: CuriousState, config: CuriousConfig) -> bool:
    interval = config.overseer_every_n_cycles
    fail_streak = config.overseer_on_review_fail_streak
    if interval <= 0 and fail_streak <= 0:
        return False
    if interval > 0 and state.cycle > 0 and state.cycle % interval == 0:
        return True
    if fail_streak > 0 and count_trailing_review_fails(state.history) >= fail_streak:
        return True
    return False


def overseer_trigger_reason(state: CuriousState, config: CuriousConfig) -> str:
    interval = config.overseer_every_n_cycles
    fail_streak = config.overseer_on_review_fail_streak
    trailing = count_trailing_review_fails(state.history)
    if interval > 0 and state.cycle > 0 and state.cycle % interval == 0:
        return f"completed {state.cycle} task cycle(s) (every {interval})"
    if fail_streak > 0 and trailing >= fail_streak:
        return f"{trailing} consecutive review FAIL(s)"
    return "scheduled"


def count_trailing_review_fails(history: list[CycleRecord]) -> int:
    count = 0
    for record in reversed(history):
        if record.phase != "review" or record.status != "finished":
            break
        if not is_review_fail(record.summary):
            break
        count += 1
    return count


def format_history_for_overseer(history: list[CycleRecord]) -> str:
    recent = history[-HISTORY_LIMIT:]
    if not recent:
        return "(no prior runs recorded)"
    lines = [
        "| Cycle | Phase | Status | Summary |",
        "| ----- | ----- | ------ | ------- |",
    ]
    for record in recent:
        summary = (record.summary or "—").replace("|", "\\|").replace("\n", " ")[:200]
        lines.append(
            f"| {record.cycle} | {record.phase} | {record.status} | {summary} |"
        )
    return "\n".join(lines)
