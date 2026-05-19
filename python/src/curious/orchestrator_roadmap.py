from __future__ import annotations

from curious.spec_roadmap import RoadmapStatus, analyze_roadmap
from curious.types import CuriousState, CycleRecord


def should_skip_until_done_loop(roadmap_status: RoadmapStatus) -> bool:
    return roadmap_status.complete


def should_stop_until_done_after_phase(
    state: CuriousState, spec_body: str
) -> bool:
    if not state.history:
        return False
    last = state.history[-1]
    if last.phase != "sync" or last.status != "finished":
        return False
    return analyze_roadmap(spec_body).complete
