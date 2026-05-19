from __future__ import annotations

from pathlib import Path

from curious.git_policy import GIT_POLICY_SECTION, GIT_POLICY_SPEC_CONSTRAINT
from curious.project import (
    AGENTS_FILENAME,
    README_FILENAME,
    relative_to_root,
)
from curious.types import ResolvedConfig
from curious.workflow_policy import (
    WORKFLOW_SPEC_CONSTRAINTS,
    build_workflow_policy_section,
    host_arch_label,
)

SPEC_SCHEMA = f"""## Required sections in spec/SPEC.md

1. **# Project spec**
2. **## Vision**
3. **## Requirements** — `- [ ] R1: ...`
4. **## Roadmap** — phased T* / M* tasks
5. **## Progress**
6. **## Acceptance criteria**
7. **## Orchestrator log**
8. **## Constraints** — include: {GIT_POLICY_SPEC_CONSTRAINT} {WORKFLOW_SPEC_CONSTRAINTS}
9. **## Open questions**

Do **not** add **## Agent steering** unless already needed.

### Roadmap schema

```markdown
## Roadmap

### Phase 1: <name>
- [ ] T1.1 — <task> (requirement: R1)
```
"""


def build_bootstrap_prompt(config: ResolvedConfig) -> str:
    project_root = Path(config.project_root)
    spec_rel = relative_to_root(project_root, Path(config.spec_path))
    agents_path = project_root / AGENTS_FILENAME
    readme_path = project_root / README_FILENAME

    agents_content = (
        agents_path.read_text(encoding="utf-8")
        if agents_path.is_file()
        else "(AGENTS.md not found — infer conventions from code only)"
    )
    readme_content = (
        readme_path.read_text(encoding="utf-8")
        if readme_path.is_file()
        else "(README.md not found — infer purpose from code only)"
    )

    return f"""# Curious bootstrap — generate initial spec

You are the **spec author** agent. Produce the first `{spec_rel}` for this project.

## Steps

1. Read README and AGENTS.md below; explore the codebase with tools.
2. **Write** `{spec_rel}` (create `spec/` if needed) following the schema.
3. Do **not** implement product code — only author the spec.
4. End with a short summary.

{build_workflow_policy_section(host_arch_label())}

{GIT_POLICY_SECTION}

{SPEC_SCHEMA}

## Workspace

- project root: `{config.project_root}`
- agent cwd: `{config.cwd}`
- output file: `{spec_rel}`

## README.md

{readme_content}

## AGENTS.md

{agents_content}
"""


def build_roadmap_prompt(config: ResolvedConfig, spec_body: str) -> str:
    spec_rel = relative_to_root(
        Path(config.project_root), Path(config.spec_path)
    )
    return f"""# Curious roadmap — expand spec into checkable tasks

You are the **roadmap planner** agent.

## Steps

1. Read the spec below and codebase as needed.
2. Update `{spec_rel}` in place: Roadmap with T* tasks, Progress for first phase only.
3. Do **not** implement product code.
4. Tasks must fit one develop→review cycle each.

{build_workflow_policy_section(host_arch_label())}

{GIT_POLICY_SECTION}

{SPEC_SCHEMA}

## Workspace

- project root: `{config.project_root}`
- agent cwd: `{config.cwd}`

## Current spec

{spec_body}
"""
