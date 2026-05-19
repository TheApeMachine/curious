# Project spec

## Vision

**Curious** is a portable, spec-driven agent workflow CLI built on the [Cursor TypeScript SDK](https://cursor.com/docs/sdk/typescript). It lets any repository adopt a repeatable loop: an agent bootstraps a living `spec/SPEC.md`, plans a phased roadmap, then autonomously implements tasks through **develop → review → sync** cycles, with periodic **overseer** meta-review to realign the spec when the repo drifts.

The tool targets developers who want autonomous Cursor agents to implement features against an explicit spec without agents committing to git or requiring CI. Curious injects binding **Workflow** and **Git policy** into every phase so reviews judge the **working tree** on the **local host architecture** only.

### Dogfooding (this repository)

**This repo is the primary target for Curious improving itself.** This file is the living contract; agents implement roadmap tasks against `src/`, `README.md`, and related project files — not against other projects unless explicitly redirected.

| Step                            | Command (from repo root)                                                     |
|---------------------------------|------------------------------------------------------------------------------|
| Build & link CLI                | `npm install && npm run build && npm link`                                   |
| One task (smoke)                | `curious run --cycle`                                                        |
| Batch through current roadmap   | `curious run`                                                                |
| **Continuous self-improvement** | `curious run --continuous` (keeps going after roadmap milestones; see below) |
| Single phase                    | `curious run --once` (uses `.curious/state.json` phase)                      |
| After code changes to curious   | `npm run build && npm link` before the next `curious run`                    |

**Loop on this codebase:** develop → review → sync → (overseer when triggered) → develop …

**Continuous improvement:** Curious should keep making the product better, not stop when one roadmap snapshot is `[x]`. Use **`curious run --continuous`** for open-ended dogfooding. When **## Roadmap** has no unchecked `T*` / `M*` tasks, the **overseer** (or human) pulls the next items from **## Next features** into a new roadmap phase and sets **## Progress** — then the loop continues. The human commits when satisfied; agents deliver uncommitted work in the working tree.

**When agents are unsure**, they read source files and `git diff` — file content is the source of truth, not prior summaries or `HEAD`.

### What exists today (v0.1.0)

The core CLI and orchestrator are implemented in TypeScript (`src/`, compiled to `dist/`):

| Area         | Implementation                                                                                                                                                   |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Commands     | `bootstrap`, `roadmap`, `run`, `status`, `reset`, `inspect`, `init` (`src/index.ts`)                                                                             |
| Orchestrator | Phase loop, run modes (`--until-done`, `--continuous`, `--cycle`, `--cycles`, `--once`), roadmap completion detection (`src/orchestrator.ts`)                    |
| Agents       | Cursor SDK integration, stable agent id, subagents (developer/reviewer/overseer), fixed `composer-2.5` model (`src/agent.ts`, `src/model.ts`)                    |
| Spec parsing | Roadmap task IDs (`T*`, `M*`), section extraction, agent steering injection/sanitization (`src/spec-roadmap.ts`, `src/spec-sections.ts`, `src/spec-steering.ts`) |
| Prompts      | Bootstrap/roadmap task builders, develop/review/sync/overseer rubrics (`src/prompts.ts`, `src/prompts-tasks.ts`)                                                 |
| Policies     | Git safety, host-only verification, steering sanitization, source-of-truth guidance (`src/git-policy.ts`, `src/workflow-policy.ts`)                              |
| Resilience   | Transient error detection, connection guard, retry backoff, `force` send for stuck runs (`src/transient-errors.ts`, `src/connection-guard.ts`)                   |
| State        | `.curious/state.json` persistence (`src/state.ts`)                                                                                                               |
| Config       | `curious.config.json` + env overrides, parent-directory discovery (`src/config.ts`, `src/project.ts`)                                                            |
| Harvest      | `curious harvest --format dpo` — JSONL export from `.curious/state.json` + optional git join (`src/harvest/`, `src/review-verdict.ts`)                         |
| Agent guidelines | `AGENTS.md` at project root — TypeScript/ESM conventions, verification commands, review rubric (inlined in develop/review/overseer prompts)                |
| Unit tests       | `npm test` — `node:test` + `node:assert/strict`; harness + `src/spec-roadmap.test.ts` (8) + `src/spec-sections.test.ts` (12) + `src/review-feedback.test.ts` (11) + `src/workflow-policy.test.ts` (13) + `src/spec-steering.test.ts` (12) + `src/state.test.ts` (11) + `src/overseer.test.ts` (17) + `src/smoke.test.ts` (7: harness + 6 dogfood smoke) |

### Gaps (what dogfooding should close)

- Phase 1 complete (**T1.1**–**T1.10**); **T2.1**–**T2.2** resilience module unit tests remain.
- Orchestrator edge cases and `inspect` diagnostics lack regression coverage — **T2.3**–**T2.5**.
- README typo (“caramba’s”) and config example gaps — **T3.1**–**T3.2**.
- Cloud runtime configured in types but not validated here — **T3.4**.
- Package pre-1.0; publish process not codified — **Phase 4**.

## Requirements

- [x] R1: CLI exposes `bootstrap`, `roadmap`, `run`, `status`, `reset`, `inspect`, and `init` with documented run modes.
- [x] R2: Orchestrator runs **develop → review → sync** cycles, persists phase/cycle in `.curious/state.json`, and resumes after interruption.
- [x] R3: `bootstrap` and `roadmap` agents write or update `spec/SPEC.md` following the required section schema without editing product source.
- [x] R4: `run` stops when all `T*` / `M*` tasks in **## Roadmap** are checked (`[x]`), or per explicit mode flags (`--cycle`, `--cycles`, `--continuous`, `--once`).
- [x] R5: Develop agent implements exactly one unchecked **## Progress** task; review agent emits a structured `review-verdict` with six criteria; sync agent updates Roadmap, Progress, and Orchestrator log.
- [x] R6: Cursor SDK integration uses a stable agent id, `composer-2.5` (non-overridable), and local runtime with project `cwd` and `settingSources`.
- [x] R7: Overseer runs on configurable interval and review-fail streak; analyzes failure patterns and spec drift; **backtracks** misaligned Roadmap/Progress checkboxes; may edit spec sections and optional **## Agent steering**; does not edit product source.
- [x] R8: Git policy is injected into all agent prompts — read-only git for agents; human commits; reviewers judge `git diff` and working tree, not `HEAD`.
- [x] R9: Workflow policy enforces host-only verification; on arm64, amd64-tagged tests are optional for review PASS; steering lines demanding commits/CI/worktrees are stripped; agents resolve doubt by reading files.
- [x] R10: Connection resilience — transient errors retry with backoff; stuck local runs recover via `force`; `inspect` surfaces failed run transcripts.
- [x] R11: Configuration merges defaults, `curious.config.json`, and environment variables (`CURSOR_API_KEY` required).
- [ ] R12: README documents install (`npm link` / global), env vars, troubleshooting, and spec shape accurately.
- [ ] R13: Automated unit tests cover pure-logic modules (spec parsing, review feedback, overseer triggers, workflow/git policy helpers).
- [x] R14: `AGENTS.md` at project root defines TypeScript/CLI conventions for develop and review agents working on this repo.
- [ ] R15: When a develop cycle changes user-facing behavior, prompts, or policies, the same cycle or sync updates **Vision (What exists)**, **Requirements**, and **README** so this spec stays accurate for the next dogfood run.
- [ ] R16: **Continuous improvement** — when the roadmap is fully checked off, the overseer (or a dedicated roadmap task) promotes prioritized items from **## Next features** into **## Roadmap** + **## Progress** so `curious run --continuous` never stalls for lack of work.
- [x] R17: **`curious harvest`** exports fine-tuning examples from orchestrator history without changing the agent loop; opt-in via `harvest` config; default output under `.curious/harvest/`.

## Fine-tuning harvest (byproduct)

Curious cycles are **`(state, action, reward, correction)`** tuples: develop diff + commentary, structured `review-verdict`, next develop fix. **`curious harvest`** reads `.curious/state.json` (and joins git SHAs when available) — **no change to develop/review/sync**.

| Format | Status | Record |
|--------|--------|--------|
| **DPO** (`--format dpo`) | **MVP shipped** | `{prompt, chosen, rejected, rationale, quality_score, metadata}` |
| Process-reward / verifier | Planned | Per-criterion FAIL + `file:line` from `blocking_issues` |
| Critique SFT | Planned | `{diff, spec, agents_md, verdict_block}` |
| Spec planning | Planned | Bootstrap/roadmap outputs |
| Tool-use traces | Planned | Tool sequence before PASS vs FAIL |
| Overseer meta | Planned | `{history, spec_before, spec_after, overseer_verdict}` |

**Quality filters (DPO):** drop `error`/`cancelled` runs; workflow-only blockers; meta tasks; noisy trajectories (3+ cycles); overseer steering/backtrack between FAIL and PASS. **`quality_score`** 0–1 on each row.

**Privacy:** `harvest.enabled` defaults off in config; all content stays local under `.curious/harvest/`. Not RLHF-in-the-loop — training is external.

```bash
curious harvest --format dpo --min-quality 0.5 -o .curious/harvest/dpo.jsonl
```

## Next features

Prioritized **product** improvements for Curious (not meta “run until done” tasks). Each item should become one or more roadmap tasks when promoted. Reorder as learnings from dogfooding dictate.

| ID   | Feature                                                                                                                                                                         | Why                                          |
|------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| NF1  | **Stuck-loop guard** — detect N consecutive review FAILs with the same `next_develop` + similar `blocking_issues`; print a clear “human gate” message instead of burning cycles | Stops T2.1-style amd64/commit loops on arm64 |
| NF2  | **Sync idempotency check** — after sync, verify Orchestrator log row + Progress match the review verdict (read spec file)                                                       | Partial spec edits on ECONNRESET             |
| NF3  | **`curious doctor`** — subcommand: config paths, spec parse, roadmap summary, last error, host arch, whether `npm link` build is stale                                          | Faster debugging without full agent run      |
| NF4  | **Roadmap replenish prompt** — when roadmap complete, overseer rubric step: promote top N from this table into `### Phase N: …` and Progress                                    | Enables R16 / continuous mode                |
| NF5  | **Develop skip heuristics** — if latest FAIL blocking issues are workflow-only (commit/CI/amd64-on-arm), inject stronger override and avoid 200s no-op reruns                   | Wasted develop time                          |
| NF6  | **Git hook template** — `curious init` optionally writes a shell hook snippet blocking mutating `git` for agent shells                                                          | Harder safety than prompts alone             |
| NF7  | **Review verdict parser** — structured parse of `review-verdict` in TS for sync/overseer (less brittle than regex in prompts)                                                   | Reliable sync checkoffs                      |
| NF8  | **State: last review snapshot** — store parsed verdict in `.curious/state.json` for develop injection without scanning full history                                             | Faster, smaller prompts                      |
| NF9  | **Config validation** — validate `curious.config.json` on load with actionable errors                                                                                           | Fewer mystifying SDK failures                |
| NF10 | **Stream progress: tool budget** — cap verbose tool spam; always show tool name + duration                                                                                      | Long review/develop logs                     |
| NF11 | **Phase timeout config** — optional max wall time per phase with clean stop                                                                                                     | Runaway activation-style tests               |
| NF12 | **Export run report** — `curious inspect --last` markdown summary for humans                                                                                                    | Post-mortem without JSONL                    |
| NF13 | **Multi-project config** — named profiles in config for switching dogfood targets                                                                                               | Curious improves other repos                 |
| NF14 | **npm publish pipeline** — CI-optional local script: test, build, pack, version bump                                                                                            | Phase 4 release                              |

**Promotion rule:** When Phases 1–5 roadmap tasks are all `[x]`, overseer’s first action is to add **Phase 6: Continuous product** (or next phase number) with concrete tasks derived from the top **unchecked** NF rows, then set **Progress** to the first of those tasks.

## Roadmap

Tasks use stable IDs. The sync phase checks these off when review passes. **All tasks below target this repository** unless noted otherwise. Each task should complete in one **develop → review → sync** cycle.

### Phase 1: Agent guidelines & test foundation

- [x] T1.1 — Add `AGENTS.md` with TypeScript, Node ESM, CLI layout, verification commands (`build`, `typecheck`, `test`), and Curious review expectations (requirement: R14)
- [x] T1.2 — Add `npm test` using `node:test` + `node:assert`; wire `package.json` script and document in `AGENTS.md` (requirement: R13)
- [x] T1.3 — Unit tests for `spec-roadmap` (`analyzeRoadmap`, task ID parsing, completion detection) (requirement: R13)
- [x] T1.4 — Unit tests for `spec-sections` (`extractSpecSection`, `stripSpecSection`) (requirement: R13)
- [x] T1.5 — Unit tests for `review-feedback` (FAIL detection, latest failed review formatting) (requirement: R13)
- [x] T1.6 — Unit tests for `workflow-policy` (`sanitizeSteering`, host arch helpers, policy section builders) (requirement: R9, R13)
- [x] T1.7 — Unit tests for `spec-steering` (parse, strip, phase-specific injection) (requirement: R13)
- [x] T1.8 — Unit tests for `state` (`nextPhase`, `initialState`, path helpers) (requirement: R2, R13)
- [x] T1.9 — Unit tests for `overseer` triggers (`shouldRunOverseer`, streak counting, history formatting) (requirement: R7, R13)
- [x] T1.10 — Dogfood smoke: `curious run --cycle` completes develop→review→sync for one Progress task; `npm run build` and `npm test` pass on this host (requirement: R1, R2, R5)

### Phase 2: Orchestrator & resilience

- [ ] T2.1 — Unit tests for `transient-errors` (`isTransientError`, `isAgentBusyError`, message extraction) (requirement: R10, R13)
- [ ] T2.2 — Unit tests for `connection-guard` retry delay and max-retry constants (requirement: R10, R13)
- [ ] T2.3 — Tests or fixtures for orchestrator **roadmap complete** early exit (`untilDone` mode) (requirement: R2, R4)
- [ ] T2.4 — Tests or fixtures for orchestrator `maxCycles` stop and phase-error resume behavior (requirement: R2, R4)
- [ ] T2.5 — Harden `inspect` and `run-diagnostics` output for common failure modes; add unit tests for formatters (requirement: R10)
- [x] T2.6 — `curious harvest --format dpo`: state + git join, quality filters, tests (`src/harvest/`, `src/review-verdict.ts`) (requirement: R17)

### Phase 3: Documentation & developer experience

- [ ] T3.1 — Fix README gaps (typo, spec shape table, run modes); sync **Vision (What exists)** if behavior changed (requirement: R12, R15)
- [ ] T3.2 — Document every `curious.config.json` field in `curious.config.example.json` and README config table (requirement: R11, R12)
- [ ] T3.3 — Add `docs/smoke-test.md` manual checklist: bootstrap → roadmap → `run --cycle` on a fresh sample project (requirement: R1, R3)
- [ ] T3.4 — Evaluate cloud runtime config path; document supported behavior or explicit non-goal in README and spec (requirement: R6)

### Phase 4: Release readiness

- [ ] T4.1 — Verify npm package contents (`files`, `bin`, `prepare` build) and publish prerequisites (requirement: R12)
- [ ] T4.2 — Establish versioning and changelog convention for `@theapemachine/curious` (requirement: R12)

### Phase 5: Overseer validation

- [ ] T5.1 — Add `testdata/` spec fixture with deliberate Roadmap/Progress drift; unit test overseer parsing/backtrack helpers (requirement: R7)
- [ ] T5.2 — Document manual overseer backtracking verification steps in README or `docs/` (requirement: R7)

### Phase 6: Continuous product (promoted from ## Next features)

_Phase 6 tasks are added by overseer or human when Phases 1–5 are complete. Seed tasks below — adjust IDs when promoting._

- [ ] T6.1 — Stuck-loop guard: detect repeated identical review FAILs; log human-gate message and optional stop (requirement: R16; feature NF1)
- [ ] T6.2 — Sync idempotency: verify Orchestrator log + Progress after sync phase (requirement: R16; feature NF2)
- [ ] T6.3 — `curious doctor` subcommand for config, spec, roadmap, and health summary (requirement: R16; feature NF3)
- [ ] T6.4 — Overseer “replenish roadmap” step: promote next items from **## Next features** when Roadmap is all `[x]` (requirement: R16; feature NF4)
- [ ] T6.5 — Wire `parseReviewVerdict` into sync/overseer paths (parser exists; feature NF7)
- [ ] T6.7 — Harvest: critique-SFT and process-reward JSONL exporters (feature NF15)
- [ ] T6.6 — Persist last review verdict in `.curious/state.json` (requirement: R2; feature NF8)

## Progress

- [x] T1.1 — Add `AGENTS.md` with TypeScript, Node ESM, CLI layout, verification commands (`build`, `typecheck`, `test`), and Curious review expectations (requirement: R14)
- [x] T1.2 — Add `npm test` using `node:test` + `node:assert`; wire `package.json` script and document in `AGENTS.md` (requirement: R13)
- [x] T1.3 — Unit tests for `spec-roadmap` (`analyzeRoadmap`, task ID parsing, completion detection) (requirement: R13)
- [x] T1.4 — Unit tests for `spec-sections` (`extractSpecSection`, `stripSpecSection`) (requirement: R13)
- [x] T1.5 — Unit tests for `review-feedback` (FAIL detection, latest failed review formatting) (requirement: R13)
- [x] T1.6 — Unit tests for `workflow-policy` (`sanitizeSteering`, host arch helpers, policy section builders) (requirement: R9, R13)
- [x] T1.7 — Unit tests for `spec-steering` (parse, strip, phase-specific injection) (requirement: R13)
- [x] T1.8 — Unit tests for `state` (`nextPhase`, `initialState`, path helpers) (requirement: R2, R13)
- [x] T1.9 — Unit tests for `overseer` triggers (`shouldRunOverseer`, streak counting, history formatting) (requirement: R7, R13)
- [x] T1.10 — Dogfood smoke: `curious run --cycle` completes develop→review→sync for one Progress task; `npm run build` and `npm test` pass on this host (requirement: R1, R2, R5)
- [ ] T2.1 — Unit tests for `transient-errors` (`isTransientError`, `isAgentBusyError`, message extraction) (requirement: R10, R13)

**Phase 1 complete.** Continue with `curious run` for batch progress, or `curious run --continuous` to keep improving through Phase 6+ as overseer promotes **## Next features**.

## Acceptance criteria

A requirement or roadmap task is **done** when:

1. The deliverable is present in the **working tree** (uncommitted changes are valid — human commits separately).
2. **Review OVERALL: PASS** on all six criteria, including **5_verification** via host-runnable tests or documented manual verification on this machine.
3. **6_git_safety: PASS** — no mutating git commands were used by agents during the cycle.
4. Spec sections (**Roadmap**, **Progress**, **Orchestrator log**) reflect completed work after sync.
5. Changes match existing code style: strict TypeScript, NodeNext ESM, minimal scope, no unrelated refactors.
6. README or inline docs are updated when user-facing behavior or config changes (**R15**).
7. Evidence cites **file paths** (and line ranges where useful) — not assumptions from chat or `HEAD` alone.

### Verification commands (this repo)

| Check                  | Command                                                                                                         |
|------------------------|-----------------------------------------------------------------------------------------------------------------|
| Compile                | `npm run build`                                                                                                 |
| Types                  | `npm run typecheck`                                                                                             |
| Unit tests             | `npm test` — must pass on this host                                                            |
| CLI still runs         | `node dist/index.js --help`                                                                                     |
| Dogfood smoke          | `curious run --cycle` from repo root with `CURSOR_API_KEY` set                                                  |
| Continuous improvement | `curious run --continuous` — use after smoke passes; replenishes from **## Next features** when roadmap is done |
| Harvest DPO              | `curious harvest --format dpo` — export after dogfood; writes `.curious/harvest/dpo.jsonl` |

On **arm64**, do not require amd64-only or CI output for PASS. Cross-arch code: verify sources, tags, and host-runnable packages.

## Orchestrator log

| Cycle | Task       | Review | Notes                                                                                         |
|-------|------------|--------|-----------------------------------------------------------------------------------------------|
| 0     | bootstrap  | —      | Initial `spec/SPEC.md` generated                                                              |
| 0     | spec-prime | —      | Primed for dogfooding: Vision, Requirements, Roadmap, Progress, acceptance, R15               |
| 0     | roadmap    | —      | Expanded Roadmap into single-cycle tasks T1.1–T5.2; Progress = Phase 1 only                   |
| 0     | spec       | —      | Added **## Next features**, Phase 6 seed, R16 continuous improvement, `--continuous` guidance |
| 3     | T1.1       | PASS   | Added `AGENTS.md` (137 lines); build/typecheck pass on arm64; R14 checked; next **T1.2** |
| 4     | T1.2       | PASS   | Wired `npm test` (node:test); smoke test; AGENTS.md Running tests; next **T1.3** |
| 5     | overseer   | ALIGNED | Checkbox audit: T1.1–T1.2 deliverables in tree; npm test pass; Progress → **T1.3**; no backtrack |
| 5     | T1.3       | PASS   | `src/spec-roadmap.test.ts` (8 tests); npm test 9 pass on arm64; next **T1.4** |
| 6     | T1.4       | PASS   | `src/spec-sections.test.ts` (12 tests); npm test 21 pass on arm64; next **T1.5** |
| 7     | T1.5       | PASS   | `src/review-feedback.test.ts` (11 tests); npm test 32 pass on arm64; next **T1.6** |
| 8     | T1.6       | PASS   | `src/workflow-policy.test.ts` (13 tests); npm test 45 pass on arm64; next **T1.7** |
| 9     | T1.7       | PASS   | `src/spec-steering.test.ts` (12 tests); npm test 57 pass on arm64; next **T1.8** |
| 10    | overseer   | ALIGNED | Checkbox audit: T1.1–T1.7 deliverables in tree; npm test 57 pass on arm64; Progress → **T1.8**; no backtrack |
| 10    | T1.8       | PASS   | `src/state.test.ts` (11 tests); npm test 68 pass on arm64; next **T1.9** |
| 11    | T1.9       | PASS   | `src/overseer.test.ts` (17 tests); npm test 85 pass on arm64; next **T1.10** |

## Constraints

### Technology

- **Runtime:** Node.js ≥ 18, TypeScript 5.x, ESM (`"type": "module"`, `NodeNext` resolution).
- **SDK:** `@cursor/sdk` for agent create/resume, streaming runs, local and optional cloud runtime.
- **Model:** `composer-2.5` only — fixed in `src/model.ts`; config `model` field is ignored.
- **Layout:** Source in `src/`, compiled output in `dist/` (gitignored); CLI entry `dist/index.js`.
- **State:** `.curious/state.json` at project root (gitignored) — orchestrator only; do not treat as product deliverable.

### Style & process

- Match existing module boundaries: pure helpers in dedicated files, prompts separated from orchestration.
- Prefer Node built-ins (`node:test` + `node:assert`) before adding heavy test dependencies unless **AGENTS.md** specifies otherwise.
- Place tests beside modules as `src/**/*.test.ts` — per **AGENTS.md** (co-located, not top-level `test/`).
- Do not edit `dist/` by hand — run `npm run build`.
- Comments only for non-obvious behavior; keep functions focused.
- **Self-improvement edits** stay in scope of the active Progress task; avoid drive-by refactors across unrelated modules.

### Workflow (binding)

- Human commits only; agents use read-only git (`status`, `diff`, `log`) and must not reset, restore, commit, add, or use worktrees.
- Agents verify on the local host architecture only (no CI required for review PASS).
- On arm64, amd64-tagged tests are optional for agent review; host-runnable tests and code inspection suffice.
- When uncertain, read source files and `git diff` — **file content is the source of truth**.
- After changing curious itself, the human runs `npm run build && npm link` before the next `curious run` so the CLI matches `src/`.

### Non-goals (initial)

- Replacing or wrapping the Cursor IDE itself.
- Multi-model support or configurable model selection.
- Agent-initiated git commits, PRs, or branch management (human owns version control).
- Requiring GitHub Actions or cross-architecture test output for review PASS on this host.
- Building a hosted SaaS orchestrator — Curious is a local CLI first.
- Using git worktrees for agent isolation in this repo.
- Meta roadmap tasks that only say “run `curious run` until done” — completion is operational, not a single implementable cycle.

## Open questions

1. **Test layout:** **Resolved** — co-locate `src/**/*.test.ts` per **AGENTS.md** (T1.1); `node:test` + `node:assert/strict`.
2. **Cloud runtime:** Defer validation to **T3.4**; treat as experimental until documented.
3. **Dogfooding:** **Resolved** — this repo runs `curious run` on its own roadmap; human commits and `npm link` after CLI changes.
4. **npm publish:** Defer to Phase 4 (**T4.1**–**T4.2**) after test coverage from Phase 1–2.
5. **Overseer proof:** **T5.1**–**T5.2** combine fixture tests and a documented manual scenario instead of a single long agent run.
6. **Continuous mode:** **Resolved** — use `curious run --continuous`; overseer promotes **## Next features** → Roadmap when Phases 1–5 are `[x]` (**T6.4** implements automation).
7. **Next feature priority:** Default order NF1→NF4→NF7→NF8 before polish (NF10–NF12); human may reprioritize this table anytime.
