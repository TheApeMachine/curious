from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from curious.harvest.quality import WORKFLOW_BLOCKER
from curious.harvest.dpo import _find_develop_before_review
from curious.project import AGENTS_FILENAME
from curious.review_feedback import is_review_fail
from curious.review_verdict import parse_review_verdict
from curious.spec_sections import extract_spec_section
from curious.types import CRITERION_KEYS, CuriousState, CycleRecord


@dataclass
class VerifierExample:
    diff: str
    spec_section: str
    agents_section: str
    labels: dict[str, bool]
    overall: bool
    metadata: dict[str, Any]


def _workflow_only_blockers(verdict) -> bool:
    if not verdict.blocking_issues:
        return False
    return all(WORKFLOW_BLOCKER.search(issue) for issue in verdict.blocking_issues)


def extract_verifier_examples(
    state: CuriousState,
    *,
    project_root: str,
    cwd: str,
    spec_path: str,
) -> list[VerifierExample]:
    spec_body = Path(spec_path).read_text(encoding="utf-8")
    spec_section = extract_spec_section(spec_body, "## Roadmap") or spec_body[:4000]
    agents_path = Path(project_root) / AGENTS_FILENAME
    agents_section = (
        agents_path.read_text(encoding="utf-8")[:4000]
        if agents_path.is_file()
        else ""
    )

    examples: list[VerifierExample] = []
    history = state.history

    for i, record in enumerate(history):
        if record.phase != "review" or record.status != "finished":
            continue
        if not record.summary:
            continue
        if record.overseer_intervened:
            continue

        verdict = parse_review_verdict(record.summary)
        if not verdict:
            continue
        if _workflow_only_blockers(verdict):
            continue

        develop_pair = _find_develop_before_review(history, i)
        if not develop_pair:
            continue
        _, develop = develop_pair

        diff = (record.diff_at_review or "").strip()
        if not diff:
            continue

        labels = {
            key: verdict.criteria.get(key) == "PASS"
            for key in CRITERION_KEYS
        }
        if not labels:
            continue

        pass_count = sum(1 for v in labels.values() if v)
        if pass_count == len(labels) or pass_count == 0:
            pass  # keep balanced-ish
        if all(labels.values()) and labels.get("6_git_safety") is False:
            continue

        examples.append(
            VerifierExample(
                diff=diff,
                spec_section=spec_section,
                agents_section=agents_section,
                labels=labels,
                overall=verdict.overall == "PASS",
                metadata={
                    "cycle": record.cycle,
                    "task_id": develop.run_id,
                    "develop_run_id": develop.run_id,
                },
            )
        )

    return examples


def examples_to_jsonl_rows(examples: list[VerifierExample]) -> list[dict]:
    return [asdict(e) for e in examples]
