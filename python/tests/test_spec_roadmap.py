from curious.spec_roadmap import analyze_roadmap

SPEC = """
## Roadmap

### Phase 1
- [x] T1.1 — done
- [ ] T1.2 — next

## Progress
- [ ] T1.2
"""


def test_analyze_roadmap():
    status = analyze_roadmap(SPEC)
    assert status.total_tasks == 2
    assert status.checked_tasks == 1
    assert status.unchecked_task_ids == ["T1.2"]
    assert not status.complete
