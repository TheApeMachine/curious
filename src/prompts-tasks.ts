import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  AGENTS_FILENAME,
  DEFAULT_SPEC_REL,
  README_FILENAME,
  relativeToRoot,
} from "./project.js";
import { GIT_POLICY_SECTION, GIT_POLICY_SPEC_CONSTRAINT } from "./git-policy.js";
import type { ResolvedConfig } from "./config.js";

const SPEC_SCHEMA = `## Required sections in spec/SPEC.md

Write or update the file with these sections (in order):

1. **# Project spec** — title
2. **## Vision** — what and why (from README + code)
3. **## Requirements** — numbered requirements as checkboxes \`- [ ] R1: ...\`
4. **## Roadmap** — phased task list agents will check off (see roadmap schema below)
5. **## Progress** — mirror of active roadmap items (sync phase maintains this)
6. **## Acceptance criteria** — definition of done
7. **## Orchestrator log** — table for automation (leave initial row)
8. **## Constraints** — tech, style, non-goals (from AGENTS.md when present); include: ${GIT_POLICY_SPEC_CONSTRAINT}
9. **## Open questions** — unresolved decisions

Do **not** add **## Agent steering** unless the project already needs it — the overseer creates that section only when corrective guidance is required.

### Roadmap schema (required)

\`\`\`markdown
## Roadmap

Tasks use stable IDs. The sync phase checks these off when review passes.

### Phase 1: <name>
- [ ] T1.1 — <task> (requirement: R1)
- [ ] T1.2 — ...

### Phase 2: <name>
- [ ] T2.1 — ...
\`\`\`

Progress section should list the **current phase** items only, e.g.:
\`\`\`markdown
## Progress
- [ ] T1.1 — ...
\`\`\`
`;

export async function buildBootstrapPrompt(config: ResolvedConfig): Promise<string> {
  const projectRoot = config.projectRoot;
  const specRel = relativeToRoot(projectRoot, config.specPath);
  const agentsPath = path.join(projectRoot, AGENTS_FILENAME);
  const readmePath = path.join(projectRoot, README_FILENAME);

  let agentsContent = "";
  let readmeContent = "";

  try {
    agentsContent = await readFile(agentsPath, "utf8");
  } catch {
    agentsContent = "(AGENTS.md not found — infer conventions from code only)";
  }

  try {
    readmeContent = await readFile(readmePath, "utf8");
  } catch {
    readmeContent = "(README.md not found — infer purpose from code only)";
  }

  return `# Curious bootstrap — generate initial spec

You are the **spec author** agent. Your job is to produce the first \`${specRel}\` for this project.

## Steps

1. Read \`${README_FILENAME}\` and \`${AGENTS_FILENAME}\` (content below).
2. Explore the codebase (structure, main packages, tests, configs) using tools.
3. **Write** \`${specRel}\` (create \`spec/\` if needed) following the schema below.
4. Do **not** implement product code — only author the spec file.
5. End with a short summary of what you captured and what the user should refine.

${GIT_POLICY_SECTION}

${SPEC_SCHEMA}

## Workspace

- project root: \`${projectRoot}\`
- agent cwd: \`${config.cwd}\`
- output file: \`${specRel}\`

## README.md

${readmeContent}

## AGENTS.md

${agentsContent}
`;
}

export async function buildRoadmapPrompt(
  config: ResolvedConfig,
  specBody: string,
): Promise<string> {
  const specRel = relativeToRoot(config.projectRoot, config.specPath);

  return `# Curious roadmap — expand spec into checkable tasks

You are the **roadmap planner** agent. The spec exists but needs a concrete, checkable **Roadmap** and **Progress** section.

## Steps

1. Read the current spec below and the codebase as needed.
2. Update \`${specRel}\` **in place**:
   - Ensure **Requirements** have stable IDs (R1, R2, …).
   - Replace or add **## Roadmap** with phased tasks (T1.1, T1.2, …) linked to requirements.
   - Set **## Progress** to the first phase's unchecked tasks only.
   - Keep Vision, Constraints, and Acceptance criteria accurate.
3. Do **not** implement product code — only edit the spec.
4. Tasks must be small enough for one develop→review cycle each.

${GIT_POLICY_SECTION}

${SPEC_SCHEMA}

## Workspace

- project root: \`${config.projectRoot}\`
- agent cwd: \`${config.cwd}\`

## Current spec

${specBody}
`;
}
