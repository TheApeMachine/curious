from __future__ import annotations

from curious.git_policy import GIT_POLICY_SECTION
from curious.overseer import format_history_for_overseer
from curious.project import AgentsDocument
from curious.review_feedback import (
    find_latest_failed_review,
    format_failed_review_for_develop,
)
from curious.spec_steering import (
    agent_steering_for_phase,
    format_steering_prompt_block,
    strip_agent_steering,
)
from curious.types import CycleRecord, Phase
from curious.types import ResolvedConfig
from curious.workflow_policy import build_workflow_policy_section, host_arch_label
from curious.workspace import agent_branch_prompt_note_for_config

REVIEW_RUBRIC = """
## Review rubric (mandatory)

You are the **reviewer**. Judge whether the **developer** delivered acceptable work.
Inspect the working tree, `git diff`, tests, and **AGENTS.md** (inlined below).
If unsure about any claim, **read the files** — on-disk content is the source of truth.

Emit this exact block at the end of your review:

```review-verdict
OVERALL: PASS | FAIL
1_maintainability: PASS | FAIL
2_correctness_performance: PASS | FAIL
3_spec_compliance: PASS | FAIL
4_homogeneity: PASS | FAIL
5_verification: PASS | FAIL
6_git_safety: PASS | FAIL
blocking_issues:
- (concrete file:line or symbol; empty only if OVERALL: PASS)
evidence:
- (test/bench commands and outcomes; or "NOT RUN" with reason)
next_develop:
- (single roadmap task ID to implement next if FAIL, e.g. T1.2)
```

**OVERALL: PASS** only when all six criteria are PASS.
**5_verification** — PASS when tests that **run on this machine** pass. **FAIL** only for real code/test gaps — **not** for uncommitted changes or missing amd64 output on arm64.
**3_spec_compliance** — judge the **working tree**, not `HEAD`.
**6_git_safety: FAIL** if develop ran a mutating git command.
Do not implement fixes — only analyze.
"""

OVERSEER_RUBRIC = """
## Overseer rubric (mandatory)

You are the **overseer** — above developer, reviewer, and sync. You do not write product code. You **own spec corrections** when the spec drifts.

### Analyze (read files — source of truth)

1. **Repeated failure modes** — history and review FAIL summaries.
2. **Spec alignment** — Vision, Requirements, Roadmap, Progress vs repo.
3. **Checkbox backtracking** — checked off but not done, or done but not checked off.
4. **Continuous improvement** — when Roadmap is all `[x]`, promote **## Next features** into a new phase.

### You may edit the spec file only

Allowed: Vision, Requirements, Roadmap, Progress, Acceptance criteria, Agent steering, Orchestrator log, Open questions, Constraints.
Do **not** edit source files or AGENTS.md unless the spec says to.

Emit:

```overseer-verdict
OVERALL: ALIGNED | DRIFT | BLOCKED
misalignments:
- (or "none")
backtrack_actions:
- (or "none")
failure_patterns:
- (or "none")
spec_adjustments:
- (or "none")
steering_updated: yes | no | cleared
alignment_notes:
- (evidence)
next_develop:
- (single task ID)
```
"""


def _phase_goals(phase: Phase, has_agents: bool) -> str:
    agents_line = (
        "Follow **AGENTS.md** (full text below) and the spec."
        if has_agents
        else "No AGENTS.md found — follow the spec and existing conventions."
    )
    if phase == "develop":
        return f"""You are the **developer** agent.

{agents_line}

Rules:
- Implement exactly **one** unchecked roadmap task from **## Progress** (lowest ID first).
- If **Review feedback (FAIL)** appears below, fix the **same** task.
- Deliver in the **working tree**; human commits later.
- Do not edit **## Roadmap**, **## Progress**, **## Agent steering**, or **## Orchestrator log**.
- When in doubt, read files — they are the source of truth."""

    if phase == "review":
        return f"""You are the **reviewer** agent.

{agents_line}
Inspect changes against the spec and AGENTS.md.

{REVIEW_RUBRIC}

Do not edit source files or the spec."""

    if phase == "sync":
        return """You are the **sync** agent (spec maintainer).

Update the spec file at the path below only:
- If review **OVERALL: PASS**: check off completed tasks in **## Roadmap** and **## Progress**.
- If review **FAIL**: do not check off; record blocking_issues in **## Orchestrator log**.
- Update **## Orchestrator log** table.
- Do **not** edit **## Agent steering** (overseer only).
- Base entries on the review verdict and files — read the spec if unsure."""

    return f"""You are the **overseer** agent (meta).

{agents_line}
Read the spec, working tree, and history. Realign when needed.

{OVERSEER_RUBRIC}"""


def build_prompt(
    *,
    phase: Phase,
    spec_path: str,
    spec_rel_path: str,
    spec_body: str,
    cycle: int,
    cwd: str,
    project_root: str,
    config: ResolvedConfig | None = None,
    agents: AgentsDocument | None = None,
    last_summary: str | None = None,
    history: list[CycleRecord] | None = None,
) -> str:
    history = history or []
    has_agents = bool(agents and agents.content.strip())
    steering = agent_steering_for_phase(spec_body, phase)
    spec_for_prompt = strip_agent_steering(spec_body)
    failed_review = find_latest_failed_review(history) if phase == "develop" else None

    sections = [
        f"# Curious — cycle {cycle}, phase: {phase.upper()}",
        "",
        _phase_goals(phase, has_agents),
        "",
        build_workflow_policy_section(host_arch_label()),
        "",
        GIT_POLICY_SECTION,
    ]

    if config:
        branch_note = agent_branch_prompt_note_for_config(config)
        if branch_note:
            sections.append(branch_note)

    if steering:
        sections.extend(["", format_steering_prompt_block(phase, steering)])

    if failed_review:
        sections.extend(["", format_failed_review_for_develop(failed_review)])

    sections.extend(
        [
            "",
            "## Workspace",
            f"- project root: `{project_root}`",
            f"- agent cwd: `{cwd}`",
            f"- spec: `{spec_rel_path}`",
        ]
    )
    if agents:
        sections.append(f"- agents: `{agents.rel_path}`")

    if phase in ("develop", "review", "overseer"):
        if agents:
            sections.extend(
                [
                    "",
                    f"## AGENTS.md (binding — `{agents.rel_path}`)",
                    "",
                    agents.content.strip(),
                ]
            )
        else:
            sections.extend(
                [
                    "",
                    "## AGENTS.md",
                    "",
                    "(not found — proceed from spec only)",
                ]
            )

    sections.extend(["", "## Spec", spec_for_prompt])

    if phase == "overseer":
        sections.extend(
            [
                "",
                "## Orchestrator history (recent)",
                format_history_for_overseer(history),
            ]
        )

    if last_summary and last_summary.strip() and not failed_review:
        sections.extend(["", "## Previous run summary", last_summary.strip()])

    return "\n".join(sections)
