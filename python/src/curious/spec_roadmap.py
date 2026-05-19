from __future__ import annotations

import re
from dataclasses import dataclass

from curious.spec_sections import extract_spec_section

ROADMAP_TASK_LINE = re.compile(
    r"^\s*-\s+\[([ xX])\]\s+((?:T\d+\.\d+|M\d+)\b)"
)


@dataclass
class RoadmapStatus:
    total_tasks: int
    checked_tasks: int
    unchecked_task_ids: list[str]
    complete: bool


def analyze_roadmap(spec_body: str) -> RoadmapStatus:
    section = extract_spec_section(spec_body, "## Roadmap")
    if not section:
        return RoadmapStatus(0, 0, [], False)

    unchecked: list[str] = []
    checked = 0
    for line in section.split("\n"):
        m = ROADMAP_TASK_LINE.match(line)
        if not m:
            continue
        task_id = m.group(2)
        if m.group(1).lower() == "x":
            checked += 1
        else:
            unchecked.append(task_id)

    total = checked + len(unchecked)
    return RoadmapStatus(
        total_tasks=total,
        checked_tasks=checked,
        unchecked_task_ids=unchecked,
        complete=total > 0 and len(unchecked) == 0,
    )
