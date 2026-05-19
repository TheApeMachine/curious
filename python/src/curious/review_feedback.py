from __future__ import annotations

import re

from curious.types import CycleRecord
from curious.workflow_policy import REVIEW_FAIL_WORKFLOW_NOTE


def is_review_fail(summary: str | None) -> bool:
    if not summary or not summary.strip():
        return False
    return bool(re.search(r"OVERALL:\s*FAIL", summary, re.I))


def find_latest_failed_review(history: list[CycleRecord]) -> CycleRecord | None:
    for record in reversed(history):
        if record.phase != "review" or record.status != "finished":
            continue
        if is_review_fail(record.summary):
            return record
    return None


def format_failed_review_for_develop(record: CycleRecord) -> str:
    body = (record.summary or "").strip() or "(review produced no summary text)"
    return "\n".join(
        [
            "## Review feedback (FAIL — fix before next review)",
            "",
            f"The reviewer rejected the last implementation (run `{record.run_id}`, cycle {record.cycle}).",
            "Address **every** blocking issue until the work would earn **OVERALL: PASS**.",
            "Re-work the **same** task in **## Progress** — do not move to a different roadmap ID.",
            "",
            REVIEW_FAIL_WORKFLOW_NOTE,
            "",
            body,
        ]
    )
