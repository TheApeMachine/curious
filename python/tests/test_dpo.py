from __future__ import annotations

from pathlib import Path

from curious.harvest.dpo import harvest_dpo_pairs
from curious.types import CuriousState, CycleRecord


def _finished(
    *,
    cycle: int,
    phase: str,
    run_id: str,
    summary: str,
) -> CycleRecord:
    return CycleRecord(
        cycle=cycle,
        phase=phase,  # type: ignore[arg-type]
        run_id=run_id,
        status="finished",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:05:00Z",
        summary=summary,
    )


def test_harvest_dpo_fail_then_pass(tmp_path: Path) -> None:
    state = CuriousState(
        phase="develop",
        cycle=2,
        history=[
            _finished(
                cycle=1,
                phase="develop",
                run_id="run-dev-fail",
                summary="## T2.1 develop\nbroken kernel",
            ),
            _finished(
                cycle=1,
                phase="review",
                run_id="run-rev-fail",
                summary="\n".join(
                    [
                        "```review-verdict",
                        "OVERALL: FAIL",
                        "5_verification: FAIL",
                        "blocking_issues:",
                        "- pkg/foo.s:12 — unmasked tail",
                        "next_develop:",
                        "- T2.1",
                        "```",
                    ]
                ),
            ),
            _finished(
                cycle=2,
                phase="develop",
                run_id="run-dev-pass",
                summary="## T2.1 fix\nmasked tail in pkg/foo.s",
            ),
            _finished(
                cycle=2,
                phase="review",
                run_id="run-rev-pass",
                summary="\n".join(
                    [
                        "```review-verdict",
                        "OVERALL: PASS",
                        "blocking_issues:",
                        "-",
                        "next_develop:",
                        "- T2.2",
                        "```",
                    ]
                ),
            ),
        ],
    )

    pairs = harvest_dpo_pairs(
        state,
        project_root=str(tmp_path),
        cwd=str(tmp_path),
        spec_path=str(tmp_path / "spec/SPEC.md"),
        min_quality=0,
        include_rejected=True,
    )

    assert len(pairs) == 1
    assert pairs[0].task_id == "T2.1"
    assert "broken kernel" in pairs[0].rejected
    assert "masked tail" in pairs[0].chosen
    assert pairs[0].rationale == ["pkg/foo.s:12 — unmasked tail"]


def test_harvest_dpo_skips_error_records(tmp_path: Path) -> None:
    state = CuriousState(
        history=[
            CycleRecord(
                cycle=0,
                phase="develop",
                run_id="run-err",
                status="error",
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:01:00Z",
            ),
        ],
    )

    pairs = harvest_dpo_pairs(
        state,
        project_root=str(tmp_path),
        cwd=str(tmp_path),
        spec_path=str(tmp_path / "spec/SPEC.md"),
        min_quality=0,
        include_rejected=True,
    )
    assert pairs == []
