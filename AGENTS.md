# AGENTS.md — Curious repository

Binding conventions for **develop**, **review**, and **overseer** agents working on this repo. Curious inlines this file into phase prompts; follow it together with `spec/SPEC.md`.

## Project layout

```text
curious/
  src/                    # TypeScript source (compiled to dist/)
    index.ts              # CLI entry (#!/usr/bin/env node)
    orchestrator.ts       # develop → review → sync loop
    agent.ts              # Cursor SDK agent + subagents
    commands/             # bootstrap, roadmap one-shot commands
    *.ts                  # pure helpers (spec parsing, policies, state, …)
    **/*.test.ts          # unit tests (co-located with modules)
  dist/                   # tsc output (gitignored; do not edit by hand)
  spec/SPEC.md            # living spec (agents do not edit Roadmap/Progress/log in develop)
  curious.config.json     # local config (gitignored in dogfood; see example)
  .curious/state.json     # orchestrator state (gitignored)
  package.json            # ESM package, bin → dist/index.js
  tsconfig.json
  README.md
```

| Area | Location | Notes |
|------|----------|-------|
| CLI commands | `src/index.ts` | Parses argv, dispatches to orchestrator or commands |
| One-shot agents | `src/commands/` | `bootstrap`, `roadmap` |
| Prompts | `src/prompts.ts`, `src/prompts-tasks.ts` | Rubrics and task builders; keep strings out of orchestration |
| Pure logic | Dedicated modules | e.g. `spec-roadmap.ts`, `workflow-policy.ts` — prefer unit-testable helpers |
| Types | `src/types.ts` | Shared interfaces (`Phase`, `CuriousConfig`, `CuriousState`, …) |
| Config | `src/config.ts`, `src/project.ts` | Defaults, env overrides, path discovery |

## TypeScript & Node ESM

- **Runtime:** Node.js ≥ 18.
- **Module system:** ESM only — `"type": "module"` in `package.json`, `"module": "NodeNext"` / `"moduleResolution": "NodeNext"` in `tsconfig.json`.
- **Imports:** Use `.js` extensions in relative imports (TypeScript NodeNext requirement), e.g. `import { foo } from "./foo.js"`.
- **Strict mode:** `"strict": true` — no implicit `any`, respect nullability.
- **Target:** ES2022; output to `dist/` with declarations.
- **Shebang:** CLI entry `src/index.ts` starts with `#!/usr/bin/env node`.
- **Built-ins:** Prefer `node:` prefix (`node:fs`, `node:path`, `node:test`, `node:assert`).
- **JSON:** `resolveJsonModule: true` — import config fixtures when needed.
- **Dev execution:** `tsx src/index.ts …` via npm scripts; production CLI uses compiled `dist/index.js`.
- **Model:** Fixed at `composer-2.5` in `src/model.ts` — do not add configurable model selection.

## Code style

- **Scope:** One Progress task per develop cycle — minimal diff, no drive-by refactors.
- **Module boundaries:** Match existing files; add pure helpers in dedicated modules rather than bloating `orchestrator.ts` or `prompts.ts`.
- **Naming:** `camelCase` functions/variables, `PascalCase` types/interfaces, `UPPER_SNAKE` for exported string constants (e.g. policy sections).
- **Exports:** Named exports for helpers; default export only where already established.
- **Comments:** Only for non-obvious behavior — code should read clearly without narration.
- **Errors:** Use existing patterns (`transient-errors.ts`, typed catches); avoid swallowing errors silently.
- **Do not edit `dist/`** — run `npm run build` after source changes.
- **Do not edit** `spec/SPEC.md` sections **## Roadmap**, **## Progress**, **## Agent steering**, or **## Orchestrator log** during develop (sync/overseer own those).

## Tests

- **Framework:** Node built-in `node:test` + `node:assert/strict` — no Jest/Vitest unless a future task explicitly adds one.
- **Layout:** Co-locate tests as `src/**/*.test.ts` next to the module under test (not a top-level `test/` tree).
- **Scope:** Unit-test pure logic modules first (parsing, policies, state helpers). Avoid testing the Cursor SDK or live agent runs in unit tests.
- **Naming:** `describe` / `it` blocks; file name `<module>.test.ts`.
- **Imports:** Test files import the module under test with `.js` extensions like production code.

### Running tests

```bash
npm test
```

Runs `npm run build`, then executes all `dist/**/*.test.js` files with Node's built-in test runner (`node --test`). Source tests live in `src/<module>.test.ts`; `tsc` emits them to `dist/` beside the compiled module.

Example:

```typescript
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeRoadmap } from "./spec-roadmap.js";

describe("analyzeRoadmap", () => {
  it("detects unchecked task IDs", () => {
    const body = "## Roadmap\n\n- [ ] T1.1 — task\n";
    assert.deepEqual(analyzeRoadmap(body).uncheckedTaskIds, ["T1.1"]);
  });
});
```

## Verification commands

Run from the repository root on **this host** (arm64, x64, etc.). Review **5_verification** passes when these succeed here — not when CI or cross-arch tests run elsewhere.

| Check | Command | When |
|-------|---------|------|
| Compile | `npm run build` | After any `src/` change |
| Types | `npm run typecheck` | After any `src/` change |
| Unit tests | `npm test` | After adding/changing tests or logic they cover |
| CLI smoke | `node dist/index.js --help` | After CLI/orchestrator changes |
| Linked CLI | `npm run build && npm link` | Human step before dogfood `curious run` on this repo |

Paste actual command output in develop/review when tests or builds were run. If a test cannot run on this host (e.g. amd64-only build tags in another project), say so explicitly — do not block on absent cross-arch output.

## Curious workflow expectations

These apply to every agent phase on this repo:

| Rule | Expectation |
|------|-------------|
| **Deliverables** | Valid **working tree** changes; human commits separately |
| **Git** | Read-only — `git status`, `git diff`, `git log` only; never `add`, `commit`, `reset`, `restore`, `worktree` |
| **Source of truth** | On-disk files and `git diff` — not chat history, not `HEAD` alone |
| **Verification** | Host-runnable tests and builds on the machine running Curious |
| **arm64** | Do not require amd64-only or CI proof when developing/reviewing on arm64 |
| **Spec edits (develop)** | Product source only — never Roadmap/Progress/Orchestrator log/Agent steering |
| **Review verdict** | Reviewer emits the `review-verdict` block with six criteria + OVERALL |
| **Task scope** | Exactly one unchecked **## Progress** task per develop cycle |

### Review rubric (what reviewers check against this file)

Reviewers judge the working tree against the active Progress task, `spec/SPEC.md`, and this document:

1. **maintainability** — focused diff, clear modules, no unnecessary complexity
2. **correctness_performance** — logic matches task intent; no obvious bugs
3. **spec_compliance** — deliverable present in tree; task requirements met
4. **homogeneity** — matches TypeScript/ESM layout, naming, and patterns above
5. **verification** — `npm run build`, `npm run typecheck`, and `npm test` (when applicable) pass on this host; evidence pasted or cited
6. **git_safety** — no mutating git commands during the cycle

**OVERALL: PASS** only when all six are PASS. Uncommitted changes are valid. Do not FAIL for missing commits, CI, or amd64 output on arm64.

### After changing the CLI

When develop changes user-facing behavior, prompts, or config, sync (or the same cycle if assigned) should update README and spec **Vision** / **Requirements** per **R15**. Develop agents may note needed doc updates in review evidence; sync owns spec checkbox edits.

## Dogfooding this repo

| Step | Command |
|------|---------|
| Build & link | `npm install && npm run build && npm link` |
| One cycle | `curious run --cycle` |
| Full Phase 1 batch | `curious run` |
| Continuous | `curious run --continuous` |

Requires `CURSOR_API_KEY` in the environment. State persists in `.curious/state.json`.
