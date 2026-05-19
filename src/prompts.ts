import type { AgentsDocument } from "./project.js";
import { formatHistoryForOverseer } from "./overseer.js";
import {
  agentSteeringForPhase,
  formatSteeringPromptBlock,
  stripAgentSteering,
} from "./spec-steering.js";
import type { CycleRecord, Phase } from "./types.js";

const REVIEW_RUBRIC = `
## Review rubric (mandatory)

You are the **reviewer**. Judge whether the **developer** delivered acceptable work.
Inspect the working tree, \`git diff\`, tests, and **AGENTS.md** (inlined below).

Emit this exact block at the end of your review:

\`\`\`review-verdict
OVERALL: PASS | FAIL
1_maintainability: PASS | FAIL
2_correctness_performance: PASS | FAIL
3_spec_compliance: PASS | FAIL
4_homogeneity: PASS | FAIL
5_verification: PASS | FAIL
blocking_issues:
- (concrete file:line or symbol; empty only if OVERALL: PASS)
evidence:
- (test/bench commands and outcomes; or "NOT RUN" with reason)
next_develop:
- (single roadmap task ID to implement next if FAIL, e.g. T1.2)
\`\`\`

**OVERALL: PASS** only when all five criteria are PASS.
Do not implement fixes — only analyze.
`;

const OVERSEER_RUBRIC = `
## Overseer rubric (mandatory)

You are the **overseer** — above the developer, reviewer, and sync agents. You do not write product code.

### Analyze
1. **Repeated failure modes** — read orchestrator history and review FAIL summaries. Cluster recurring blocking_issues, flaky tests, spec drift, scope creep, or wrong task ordering.
2. **Spec alignment** — compare Vision, Requirements, Roadmap, Progress, and Acceptance criteria to what the team actually shipped (history + \`git log\` / diff if needed).
3. **Process health** — are tasks the right size? Is Progress pointing at the right next task? Are phases stuck or redoing work?

### You may edit \`spec/SPEC.md\` only
Allowed sections: **Vision**, **Requirements**, **Roadmap**, **Progress**, **Acceptance criteria**, **Agent steering**, **Orchestrator log**, **Open questions**, **Constraints**.
- Reprioritize or split/merge roadmap tasks when alignment requires it.
- Clarify requirements or acceptance criteria when reviews keep failing for the same reason.
- Reset **Progress** to the correct next task(s) for the developer.
- **\`## Agent steering\` is optional** — add or update it **only** when develop/review/sync need concrete corrective guidance (repeated failures, drift, confusion). When the team is healthy, **do not** add steering; clear stale bullets or leave the section empty / \`(none)\`.
- Do **not** check off roadmap tasks (sync owns that after review PASS).
- Do **not** edit source files, AGENTS.md, or README unless the spec explicitly says to.

### Agent steering (exception, not default)

Steering is injected into downstream prompts **only when** you write actionable bullets. Empty or \`(none)\` means no injection — agents follow the spec and AGENTS.md as usual.

Use **only** when something must improve, e.g. recurring review FAILs, wrong task focus, missing verification habits:

\`\`\`markdown
## Agent steering

### Developer
- (specific corrective bullet — omit subsection if nothing for developer)

### Reviewer
- (specific bullet — omit if nothing)

### Sync
- (specific bullet — omit if nothing)
\`\`\`

When **OVERALL: ALIGNED** and failure_patterns are clean: remove outdated steering or set the section to \`(none)\`. Do not invent guidance for a well-running team.

### Emit this block at the end

\`\`\`overseer-verdict
OVERALL: ALIGNED | DRIFT | BLOCKED
failure_patterns:
- (recurring themes; "none" if clean)
spec_adjustments:
- (bullet list of spec edits made, or "none")
steering_updated: yes | no | cleared
alignment_notes:
- (how well the team matches the full spec)
next_develop:
- (single task ID the developer should take next, e.g. T1.5)
\`\`\`

**OVERALL: DRIFT** — spec updated to realign; developer should follow new Progress.
**OVERALL: BLOCKED** — fundamental spec/process issue; explain in alignment_notes.
**OVERALL: ALIGNED** — no spec edits required unless clearing stale steering; confirm next_develop. Prefer **steering_updated: no** or **cleared** when healthy.
`;

function phaseGoals(phase: Phase, hasAgents: boolean): string {
  const agentsLine = hasAgents
    ? "Follow **AGENTS.md** (full text below) and the spec. AGENTS.md is binding for style, structure, and verification."
    : "No AGENTS.md found — follow the spec and existing project conventions.";

  switch (phase) {
    case "develop":
      return `You are the **developer** agent.

${agentsLine}

Rules:
- Implement exactly **one** unchecked roadmap task from **## Progress** (lowest ID first).
- If **Agent steering** appears below, it is exceptional corrective guidance from the overseer — follow it for this run. If absent, proceed from the spec only.
- All code and tests must satisfy AGENTS.md and the spec.
- **Paste test/benchmark command output** in your final summary.
- Do not edit **## Roadmap**, **## Progress**, **## Agent steering**, or **## Orchestrator log** (sync/overseer own those).
- Do not run destructive git commands.
- If blocked, stop and state the blocker — no placeholders.`;

    case "review":
      return `You are the **reviewer** agent.

${agentsLine}
Inspect changes since the last develop run against the spec, roadmap, and AGENTS.md.
If **Agent steering** appears below, apply that corrective focus; otherwise review against the spec and AGENTS.md only.

You may use the \`reviewer\` subagent for a deeper pass if helpful.

${REVIEW_RUBRIC}

Do not edit source files or the spec.`;

    case "sync":
      return `You are the **sync** agent (spec maintainer).

Update the spec file at the path below only:
- If review **OVERALL: PASS**: check off the completed task in **## Roadmap** and **## Progress**; add the next task to Progress if the phase continues.
- If review **FAIL**: do not check off tasks; record blocking_issues in **## Orchestrator log**.
- Update **## Orchestrator log** table: cycle, task ID, review verdict, next develop target.
- If **Agent steering** appears below, follow it when recording the log; otherwise use normal sync rules.
- Do **not** edit **## Agent steering** (overseer only).
- Keep edits minimal and factual.`;

    case "overseer":
      return `You are the **overseer** agent (meta — above reviewer and sync).

${agentsLine}
Read the full spec, orchestrator history below, and recent git activity.

You may delegate analysis to the \`overseer\` subagent, but you must apply any spec edits and emit the verdict yourself.

${OVERSEER_RUBRIC}`;
  }
}

function formatAgentsSection(agents: AgentsDocument): string {
  return [
    `## AGENTS.md (binding — \`${agents.relPath}\`)`,
    "",
    agents.content.trim(),
  ].join("\n");
}

/** Phases that require AGENTS.md inlined in the prompt (not just a path). */
function phaseIncludesAgents(phase: Phase): boolean {
  return phase === "develop" || phase === "review" || phase === "overseer";
}

export function buildPrompt(args: {
  phase: Phase;
  specPath: string;
  specRelPath: string;
  specBody: string;
  cycle: number;
  cwd: string;
  projectRoot: string;
  agents?: AgentsDocument;
  lastSummary?: string;
  history?: CycleRecord[];
}): string {
  const {
    phase,
    specRelPath,
    specBody,
    cycle,
    cwd,
    projectRoot,
    agents,
    lastSummary,
    history = [],
  } = args;

  const includeAgents = phaseIncludesAgents(phase);
  const hasAgents = Boolean(agents?.content);
  const steering = agentSteeringForPhase(specBody, phase);
  const specForPrompt = stripAgentSteering(specBody);

  const sections = [
    `# Curious — cycle ${cycle}, phase: ${phase.toUpperCase()}`,
    "",
    phaseGoals(phase, hasAgents),
  ];

  if (steering) {
    sections.push("", formatSteeringPromptBlock(phase, steering));
  }

  sections.push(
    "",
    "## Workspace",
    `- project root: \`${projectRoot}\``,
    `- agent cwd: \`${cwd}\``,
    `- spec: \`${specRelPath}\``,
    ...(agents ? [`- agents: \`${agents.relPath}\``] : []),
  );

  if (includeAgents && agents) {
    sections.push("", formatAgentsSection(agents));
  } else if (includeAgents && !agents) {
    sections.push(
      "",
      "## AGENTS.md",
      "",
      "(not found at project root or agent cwd — proceed from spec only)",
    );
  }

  sections.push("", "## Spec", specForPrompt);

  if (phase === "overseer") {
    sections.push(
      "",
      "## Orchestrator history (recent)",
      formatHistoryForOverseer(history),
    );
  }

  if (lastSummary?.trim()) {
    sections.push("", "## Previous run summary", lastSummary.trim());
  }

  return sections.join("\n");
}
