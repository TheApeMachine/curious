from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from curious.project import AGENTS_FILENAME
from curious.review_verdict import extract_task_id
from curious.spec_roadmap import analyze_roadmap
from curious.spec_sections import extract_spec_section
from curious.types import CuriousState


@dataclass
class GrpoTaskExample:
    prompt: str
    task_id: str
    spec_section: str
    agents_section: str
    metadata: dict[str, Any]

    def to_json(self) -> dict:
        return asdict(self)


def _build_develop_prompt(
    task_id: str,
    spec_body: str,
    agents_content: str,
    spec_path: str,
) -> str:
    roadmap = extract_spec_section(spec_body, "## Roadmap") or ""
    constraints = extract_spec_section(spec_body, "## Constraints") or ""
    return "\n".join(
        [
            f"# Develop task {task_id}",
            "",
            f"Spec: {spec_path}",
            "",
            "## Roadmap context",
            roadmap[:6000],
            "",
            "## Constraints",
            constraints[:2000],
            "",
            "## AGENTS.md",
            agents_content[:4000] if agents_content else "(none)",
            "",
            "Implement this task in the working tree. Run tests on this host. "
            "End with a clear summary.",
        ]
    )


def harvest_grpo_tasks(
    state: CuriousState,
    *,
    project_root: str,
    spec_path: str,
) -> list[GrpoTaskExample]:
    root = Path(project_root)
    spec_body = Path(spec_path).read_text(encoding="utf-8")
    agents_path = root / AGENTS_FILENAME
    agents_content = (
        agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    )
    spec_section = extract_spec_section(spec_body, "## Roadmap") or spec_body[:8000]

    seen: set[str] = set()
    examples: list[GrpoTaskExample] = []

    status = analyze_roadmap(spec_body)
    for task_id in status.unchecked_task_ids:
        if task_id in seen:
            continue
        seen.add(task_id)
        examples.append(
            GrpoTaskExample(
                prompt=_build_develop_prompt(
                    task_id, spec_body, agents_content, spec_path
                ),
                task_id=task_id,
                spec_section=spec_section,
                agents_section=agents_content[:4000],
                metadata={"source": "roadmap", "unchecked": True},
            )
        )

    for record in state.history:
        if record.phase != "develop" or record.status != "finished":
            continue
        task_id = extract_task_id(record.summary) or f"cycle-{record.cycle}-develop"
        if task_id in seen:
            continue
        seen.add(task_id)
        examples.append(
            GrpoTaskExample(
                prompt=_build_develop_prompt(
                    task_id, spec_body, agents_content, spec_path
                ),
                task_id=task_id,
                spec_section=spec_section,
                agents_section=agents_content[:4000],
                metadata={
                    "source": "history",
                    "cycle": record.cycle,
                    "run_id": record.run_id,
                },
            )
        )

    return examples
