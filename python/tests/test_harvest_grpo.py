from __future__ import annotations

from curious.harvest.grpo import harvest_grpo_tasks
from curious.types import CuriousState, CycleRecord


def test_harvest_grpo_from_roadmap(tmp_path) -> None:
    spec = tmp_path / "spec" / "SPEC.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        """# Project spec

## Roadmap
### Phase 1
- [ ] T1.1 — first task
- [x] T1.2 — done

## Progress
- [ ] T1.1
""",
        encoding="utf-8",
    )
    state = CuriousState()
    examples = harvest_grpo_tasks(
        state,
        project_root=str(tmp_path),
        spec_path=str(spec),
    )
    assert len(examples) >= 1
    assert any(ex.task_id == "T1.1" for ex in examples)
    assert "T1.1" in examples[0].prompt


def test_harvest_grpo_from_history(tmp_path) -> None:
    spec = tmp_path / "spec" / "SPEC.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# Project spec\n\n## Roadmap\n- [ ] T2.1 — x\n",
        encoding="utf-8",
    )
    state = CuriousState()
    state.history.append(
        CycleRecord(
            cycle=1,
            phase="develop",
            run_id="r1",
            status="finished",
            started_at="t",
            finished_at="t",
            summary="Completed T2.1 in src/foo.py",
        )
    )
    examples = harvest_grpo_tasks(
        state,
        project_root=str(tmp_path),
        spec_path=str(spec),
    )
    assert any("T2.1" in ex.task_id or "T2.1" in ex.prompt for ex in examples)
