from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from curious.types import Phase

SPEC_HISTORY_DIR = ".curious/spec_history"
LABELS_FILE = ".curious/spec_history/labels.jsonl"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def snapshot_spec(
    project_root: Path,
    cycle: int,
    spec_body: str,
    phase: Phase,
) -> str:
    """Write .curious/spec_history/{cycle:04d}-{phase}.md, return sha."""
    history_dir = project_root / SPEC_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    name = f"{cycle:04d}-{phase}.md"
    path = history_dir / name
    path.write_text(spec_body, encoding="utf-8")
    return _sha(spec_body)


def snapshot_agents(project_root: Path, cycle: int, phase: Phase, content: str) -> str:
    history_dir = project_root / SPEC_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{cycle:04d}-{phase}-agents.md"
    path.write_text(content, encoding="utf-8")
    return _sha(content)


def _snapshot_path(project_root: Path, cycle: int, phase: str) -> Path | None:
    path = project_root / SPEC_HISTORY_DIR / f"{cycle:04d}-{phase}.md"
    return path if path.is_file() else None


def diff_specs(project_root: Path, from_cycle: int, to_cycle: int) -> str:
    """Unified diff between two cycle snapshots (develop phase files)."""
    a = _snapshot_path(project_root, from_cycle, "develop") or _snapshot_path(
        project_root, from_cycle, "overseer"
    )
    b = _snapshot_path(project_root, to_cycle, "develop") or _snapshot_path(
        project_root, to_cycle, "overseer"
    )
    if not a or not b:
        return ""
    result = subprocess.run(
        ["git", "diff", "--no-index", str(a), str(b)],
        capture_output=True,
        text=True,
    )
    return result.stdout or result.stderr


def overseer_diff_for_cycle(project_root: Path, overseer_cycle: int) -> str | None:
    before = _snapshot_path(project_root, overseer_cycle, "develop")
    after = _snapshot_path(project_root, overseer_cycle, "overseer")
    if not before or not after:
        return None
    result = subprocess.run(
        ["git", "diff", "--no-index", str(before), str(after)],
        capture_output=True,
        text=True,
    )
    out = result.stdout or ""
    return out if out.strip() else None


@dataclass
class OverseerLabel:
    cycle: int
    sha_before: str
    sha_after: str
    lines_added: int
    lines_removed: int
    summary: str


def append_overseer_label(project_root: Path, label: OverseerLabel) -> None:
    path = project_root / LABELS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "cycle": label.cycle,
        "shaBefore": label.sha_before,
        "shaAfter": label.sha_after,
        "linesAdded": label.lines_added,
        "linesRemoved": label.lines_removed,
        "summary": label.summary,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_overseer_labels(project_root: Path) -> list[dict]:
    path = project_root / LABELS_FILE
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def correlate_overseer_edits(
    state_history: list,
    labels: list[dict],
    *,
    window: int = 5,
) -> list[dict]:
    """Pass-rate within N cycles before vs after each overseer edit."""
    from curious.review_feedback import is_review_fail

    results = []
    for label in labels:
        cycle = int(label["cycle"])
        before_pass = 0
        before_total = 0
        after_pass = 0
        after_total = 0
        for record in state_history:
            if record.phase != "review" or record.status != "finished":
                continue
            if cycle - window <= record.cycle < cycle:
                before_total += 1
                if not is_review_fail(record.summary):
                    before_pass += 1
            elif cycle < record.cycle <= cycle + window:
                after_total += 1
                if not is_review_fail(record.summary):
                    after_pass += 1
        results.append(
            {
                "cycle": cycle,
                "summary": label.get("summary", ""),
                "before_pass_rate": before_pass / before_total if before_total else None,
                "after_pass_rate": after_pass / after_total if after_total else None,
                "lines_added": label.get("linesAdded", 0),
            }
        )
    results.sort(
        key=lambda r: (r["after_pass_rate"] or 0) - (r["before_pass_rate"] or 0),
        reverse=True,
    )
    return results


def count_diff_lines(diff_text: str) -> tuple[int, int]:
    added = removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed
