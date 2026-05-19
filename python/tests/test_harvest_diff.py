from __future__ import annotations

import tempfile
from pathlib import Path

from curious.harvest.verifier import extract_verifier_examples
from curious.types import CuriousState, CycleRecord

_PASS_VERDICT = """
```review-verdict
OVERALL: PASS
1_maintainability: PASS
2_correctness_performance: PASS
3_spec_compliance: PASS
4_homogeneity: PASS
5_verification: PASS
6_git_safety: PASS
blocking_issues:
-
evidence:
-
next_develop:
-
```
"""


def test_verifier_harvest_uses_stored_diff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        spec = root / "spec.md"
        spec.write_text("## Roadmap\n- [ ] T1.1\n", encoding="utf-8")
        state = CuriousState(
            version=2,
            history=[
                CycleRecord(
                    cycle=1,
                    phase="develop",
                    run_id="dev-1",
                    status="finished",
                    started_at="t0",
                    finished_at="t1",
                    summary="implemented",
                ),
                CycleRecord(
                    cycle=1,
                    phase="review",
                    run_id="rev-1",
                    status="finished",
                    started_at="t1",
                    finished_at="t2",
                    summary=_PASS_VERDICT,
                    diff_at_review="diff --git a/foo.py b/foo.py\n+print('historical')\n",
                ),
            ],
        )
        examples = extract_verifier_examples(
            state,
            project_root=str(root),
            cwd=str(root),
            spec_path=str(spec),
        )
        assert len(examples) == 1
        assert "historical" in examples[0].diff
