import path from "node:path";
import type { AgentsDocument } from "./project.js";
import type { Phase } from "./types.js";

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
- All code and tests must satisfy AGENTS.md and the spec.
- **Paste test/benchmark command output** in your final summary.
- Do not edit **## Roadmap**, **## Progress**, or **## Orchestrator log** (sync owns those).
- Do not run destructive git commands.
- If blocked, stop and state the blocker — no placeholders.`;

    case "review":
      return `You are the **reviewer** agent.

${agentsLine}
Inspect changes since the last develop run against the spec, roadmap, and AGENTS.md.

You may use the \`reviewer\` subagent for a deeper pass if helpful.

${REVIEW_RUBRIC}

Do not edit source files or the spec.`;

    case "sync":
      return `You are the **sync** agent (spec maintainer).

Update the spec file at the path below only:
- If review **OVERALL: PASS**: check off the completed task in **## Roadmap** and **## Progress**; add the next task to Progress if the phase continues.
- If review **FAIL**: do not check off tasks; record blocking_issues in **## Orchestrator log**.
- Update **## Orchestrator log** table: cycle, task ID, review verdict, next develop target.
- Keep edits minimal and factual.`;
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
  return phase === "develop" || phase === "review";
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
  } = args;

  const includeAgents = phaseIncludesAgents(phase);
  const hasAgents = Boolean(agents?.content);

  const sections = [
    `# Curious — cycle ${cycle}, phase: ${phase.toUpperCase()}`,
    "",
    phaseGoals(phase, hasAgents),
    "",
    "## Workspace",
    `- project root: \`${projectRoot}\``,
    `- agent cwd: \`${cwd}\``,
    `- spec: \`${specRelPath}\``,
    ...(agents ? [`- agents: \`${agents.relPath}\``] : []),
  ];

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

  sections.push("", "## Spec", specBody);

  if (lastSummary?.trim()) {
    sections.push("", "## Previous run summary", lastSummary.trim());
  }

  return sections.join("\n");
}
