import type { AgentsDocument } from "./project.js";
import { formatHistoryForOverseer } from "./overseer.js";
import {
  findLatestFailedReview,
  formatFailedReviewForDevelop,
} from "./review-feedback.js";
import {
  agentSteeringForPhase,
  formatSteeringPromptBlock,
  stripAgentSteering,
} from "./spec-steering.js";
import { GIT_POLICY_SECTION } from "./git-policy.js";
import { buildWorkflowPolicySection, hostArchLabel } from "./workflow-policy.js";
import type { CycleRecord, Phase } from "./types.js";

const REVIEW_RUBRIC = `
## Review rubric (mandatory)

You are the **reviewer**. Judge whether the **developer** delivered acceptable work.
Inspect the working tree, \`git diff\`, tests, and **AGENTS.md** (inlined below).
If unsure about any claim, **read the files** — on-disk content is the source of truth, not prior summaries or \`HEAD\` alone.

Emit this exact block at the end of your review:

\`\`\`review-verdict
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
\`\`\`

**OVERALL: PASS** only when all six criteria are PASS.

**5_verification** — apply **Workflow** (host-only): PASS when tests that **run on this machine** pass and the working tree contains the deliverable. **FAIL** only for real code/test gaps on this host — **not** for uncommitted changes, **not** for missing amd64/AVX-512 output on arm64, **not** for absent CI/GitHub Actions.

**3_spec_compliance** — judge the **working tree**, not \`HEAD\`. Uncommitted work is valid.

**6_git_safety: FAIL** if develop (or any agent this cycle) ran a mutating git command (see Git policy) or discarded uncommitted work via git.
Do not implement fixes — only analyze.
`;

const OVERSEER_RUBRIC = `
## Overseer rubric (mandatory)

You are the **overseer** — above the developer, reviewer, and sync agents. You do not write product code. You **own spec corrections** when the living spec drifts from reality or the loop needs realignment.

### Analyze (read files — source of truth)

1. **Repeated failure modes** — orchestrator history and review FAIL summaries; cluster recurring blocking_issues, flaky tests, spec drift, scope creep, wrong task ordering.
2. **Spec alignment** — Vision, Requirements, Roadmap, Progress, Acceptance criteria vs what is in the repo (**read** sources and \`git diff\`; history is hints only).
3. **Process health** — task sizing, Progress focus, stuck phases, redoing work.
4. **Checkbox backtracking** — Roadmap/Progress vs the working tree:
   - **Checked off but not done** — \`[x]\` but deliverable missing (false PASS, premature checkoff).
   - **Done but not checked off** — work present, still \`[ ]\` (missed sync).
   - **Wrong active task** — Progress points at the wrong ID.
5. **Continuous improvement** — if every \`T*\` / \`M*\` in **## Roadmap** is \`[x]\`, read **## Next features** and promote the top priority items into a new roadmap phase (concrete task IDs, one cycle each) and set **## Progress** to the first new task so the loop does not stall.

### You may edit \`spec/SPEC.md\` only

Allowed sections: **Vision**, **Requirements**, **Roadmap**, **Progress**, **Acceptance criteria**, **Agent steering**, **Orchestrator log**, **Open questions**, **Constraints**.

- **Backtrack** Roadmap/Progress when misalignment is clear from files (uncheck/check boxes, set Progress, log in Orchestrator log).
- **Replenish** Roadmap from **## Next features** when the roadmap is fully checked off (add phase + tasks + Progress).
- Reprioritize or split/merge roadmap tasks when alignment requires it.
- Clarify requirements or acceptance criteria when reviews keep failing for the same reason — **do not** add criteria requiring agent commits, CI, worktrees, or amd64 test output on arm64 hosts (see Workflow).
- Reset **Progress** to the correct next task(s).
- **\`## Agent steering\` is optional** — add or update **only** when develop/review/sync need concrete corrective guidance; clear stale bullets or \`(none)\` when healthy.
- Do **not** check off tasks on the forward path (sync owns that after review PASS).
- Do **not** edit source files, AGENTS.md, or README unless the spec explicitly says to.

### Agent steering (exception, not default)

Steering is injected into downstream prompts **only when** you write actionable bullets. Empty or \`(none)\` means no injection.

\`\`\`markdown
## Agent steering

### Developer
- (specific bullet — omit subsection if nothing)

### Reviewer
- (specific bullet — omit if nothing)

### Sync
- (specific bullet — omit if nothing)
\`\`\`

When **OVERALL: ALIGNED** and patterns are clean: remove outdated steering or set \`(none)\`; do not invent guidance for a well-running team.

### Emit this block at the end

\`\`\`overseer-verdict
OVERALL: ALIGNED | DRIFT | BLOCKED
misalignments:
- (checkbox/task vs repo; "none" if clean)
backtrack_actions:
- (Roadmap/Progress checkbox edits, or "none")
failure_patterns:
- (recurring themes; "none" if clean)
spec_adjustments:
- (other spec edits made, or "none")
steering_updated: yes | no | cleared
alignment_notes:
- (evidence: files/lines; human-needed gaps)
next_develop:
- (single task ID, e.g. T2.1)
\`\`\`

**OVERALL: DRIFT** — spec updated (backtrack and/or other sections); develop follows **next_develop**.
**OVERALL: BLOCKED** — fundamental issue; explain in alignment_notes; prefer minimal spec edits.
**OVERALL: ALIGNED** — no spec edits required unless clearing stale steering; confirm **next_develop**.
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
- If **Review feedback (FAIL)** appears below, you are **fixing the same task** after a failed review — satisfy every blocking issue and rubric item there before the next review.
- If **Agent steering** appears below, it is corrective guidance from the overseer — follow it for this run. If absent, proceed from the spec only.
- All code and tests must satisfy AGENTS.md and the spec on **this host** (see Workflow).
- **Paste test/benchmark output** for commands that actually run here.
- Deliver fixes in the **working tree**; the human commits later — never \`git add\` / \`git commit\`.
- Do not edit **## Roadmap**, **## Progress**, **## Agent steering**, or **## Orchestrator log** (sync/overseer own those).
- If blocked on code you cannot write or tests that cannot run on this host, stop and state the blocker — do not block on commit, CI, or cross-arch test output.
- **When in doubt**, read the relevant files (\`read\` / \`grep\` / \`git diff\`) — file content beats summaries or memory.`;

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
- Keep edits minimal and factual.
- Base log entries on the **review verdict and files**, not assumptions — read the spec if unsure.`;

    case "overseer":
      return `You are the **overseer** agent (meta — above reviewer and sync).

${agentsLine}
Read the full spec, working tree, and orchestrator history below. Realign the spec when needed — including **backtracking** misaligned Roadmap/Progress checkboxes.

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
  branchNote?: string;
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
    branchNote,
    agents,
    lastSummary,
    history = [],
  } = args;

  const includeAgents = phaseIncludesAgents(phase);
  const hasAgents = Boolean(agents?.content);
  const steering = agentSteeringForPhase(specBody, phase);
  const specForPrompt = stripAgentSteering(specBody);
  const failedReview =
    phase === "develop" ? findLatestFailedReview(history) : undefined;

  const hostArch = hostArchLabel();
  const sections = [
    `# Curious — cycle ${cycle}, phase: ${phase.toUpperCase()}`,
    "",
    phaseGoals(phase, hasAgents),
    "",
    buildWorkflowPolicySection(hostArch),
    "",
    GIT_POLICY_SECTION,
  ];

  if (branchNote) {
    sections.push(branchNote);
  }

  if (steering) {
    sections.push("", formatSteeringPromptBlock(phase, steering));
  }

  if (failedReview) {
    sections.push("", formatFailedReviewForDevelop(failedReview));
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

  if (lastSummary?.trim() && !failedReview) {
    sections.push("", "## Previous run summary", lastSummary.trim());
  }

  return sections.join("\n");
}
