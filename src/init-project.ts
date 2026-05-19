import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { DEFAULT_SPEC_REL, pathExists, resolveProjectAtDirectory } from "./project.js";

const SPEC_TEMPLATE = `# Project spec

Run \`curious bootstrap\` to generate this file from your codebase, or edit manually.

## Vision

## Requirements

- [ ] R1:

## Roadmap

### Phase 1: Foundation
- [ ] T1.1 — (requirement: R1)

## Progress

- [ ] T1.1 —

## Acceptance criteria

## Orchestrator log

| Cycle | Task | Review | Notes |
| ----- | ---- | ------ | ----- |
| 0     | —    | —      | —     |

## Constraints

## Open questions

`;

export async function initProject(startDir: string): Promise<void> {
  const resolved = path.resolve(startDir);
  const discovered = await resolveProjectAtDirectory(resolved);
  const specPath = discovered.specPath;

  if (await pathExists(specPath)) {
    console.log(`[curious] spec already exists at ${specPath}`);
    console.log("[curious] use: curious bootstrap  (agent-generated)");
    console.log("[curious]  or: curious roadmap   (after editing spec)");
    return;
  }

  await mkdir(path.dirname(specPath), { recursive: true });
  await writeFile(specPath, SPEC_TEMPLATE, "utf8");
  console.log(`[curious] created ${specPath}`);
  console.log("[curious] recommended: curious bootstrap");
}
