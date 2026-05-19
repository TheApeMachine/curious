from __future__ import annotations

import json
import tempfile
from pathlib import Path

from curious.state import initial_state, load_state, save_state
from curious.trajectory import ToolCallTrace, excerpt_tool_result, trim_trajectory
from curious.types import CycleRecord, STATE_VERSION


def test_tool_call_trace_round_trip() -> None:
    trace = ToolCallTrace(
        name="read_file",
        arguments={"path": "foo.py"},
        result_excerpt="content",
    )
    data = trace.to_json()
    restored = ToolCallTrace.from_json(data)
    assert restored.name == "read_file"
    assert restored.arguments == {"path": "foo.py"}


def test_trim_trajectory_keeps_bounds() -> None:
    big = "x" * 3000
    traces = [
        ToolCallTrace(name=f"t{i}", arguments={}, result_excerpt=big)
        for i in range(30)
    ]
    trimmed = trim_trajectory(traces)
    payload = json.dumps([t.to_json() for t in trimmed])
    assert len(payload.encode()) <= 50 * 1024 + 5000


def test_state_v2_trajectory_persist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state = initial_state()
        state.version = STATE_VERSION
        state.history.append(
            CycleRecord(
                cycle=0,
                phase="develop",
                run_id="run-1",
                status="finished",
                started_at="t0",
                finished_at="t1",
                summary="done",
                trajectory=[
                    ToolCallTrace("run", {"cmd": "true"}, excerpt_tool_result("ok"))
                ],
                spec_snapshot_sha="abc",
            )
        )
        save_state(root, state)
        loaded = load_state(root)
        assert loaded.version == STATE_VERSION
        assert len(loaded.history[0].trajectory) == 1
        assert loaded.history[0].spec_snapshot_sha == "abc"
