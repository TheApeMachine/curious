# curious

Portable **spec-driven** agent workflow on the [Cursor TypeScript SDK](https://cursor.com/docs/sdk/typescript). Point it at any repo: an agent bootstraps a living spec, plans a roadmap, then implements tasks in a **develop → review → sync** loop (with periodic **overseer** meta-review) until the roadmap is done.

## How it works

```text
curious bootstrap  →  curious roadmap  →  curious run
     (spec)              (tasks)         (autonomous loop)
```

| Step | Command             | What happens                                                                                                                         |
|------|---------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| 1    | `curious bootstrap` | Explores README, AGENTS.md, and code → writes `spec/SPEC.md`                                                                         |
| 2    | `curious roadmap`   | Expands the spec into phased **Roadmap** + **Progress** checkboxes                                                                   |
| 3    | `curious run`       | **Developer** → **Reviewer** → **Sync** per task; **Overseer** periodically realigns the spec; repeats until the roadmap is done |

You refine the spec after bootstrap. The loop reads **Progress** for the next task and checks off **Roadmap** when review passes.

### Dev loop phases

| Phase       | Agent     | Responsibility                                                                                                             |
|-------------|-----------|----------------------------------------------------------------------------------------------------------------------------|
| **develop** | Developer | One **Progress** task; after review **FAIL**, gets the **full review** in-prompt and re-works the same task until it passes |
| **review**  | Reviewer  | Audits the diff; outputs a `review-verdict` block (six criteria incl. git safety + **OVERALL: PASS/FAIL**)                 |
| **sync**    | Sync      | On PASS: checks off **Roadmap** / **Progress**, updates **Orchestrator log**; on FAIL: records blockers, leaves tasks open |
| **overseer** | Overseer | Meta-review: failure patterns, spec alignment, **checkbox backtracking** when Roadmap/Progress drift from the repo; may edit spec sections and optional **Agent steering**; no code |

After **sync** completes a task cycle, **overseer** may run before the next **develop** when:

- Every **N** completed task cycles (`overseerEveryNCycles`, default **5**), or
- **2** consecutive **review** FAILs (`overseerOnReviewFailStreak`, default **2**)

Set either interval to `0` in `curious.config.json` to disable that trigger.

### Overseer

Runs after sync on a schedule or after repeated review FAILs. The overseer **owns spec corrections** when the spec and repo diverge:

| Responsibility | Examples |
|----------------|----------|
| **Backtracking** | Uncheck `[x]` when work is not in the tree; check or reopen when work is done but still `[ ]`; fix **Progress** |
| **Alignment** | Failure patterns, drift vs Vision/Requirements, reprioritize or clarify roadmap/acceptance criteria |
| **Agent steering** | Optional corrective bullets for develop/review/sync when something concrete needs to improve |

Judges from **file content** (not chat history). Respects Workflow: no agent commits, host-only verification, no CI/amd64-on-arm requirements in acceptance criteria. Does not edit product source.

### Agent steering (optional, exception-only)

When the overseer finds concrete problems, it may add **`## Agent steering`** with `### Developer`, `### Reviewer`, and/or `### Sync` bullets. Curious injects only actionable bullets into that phase’s prompt. When healthy, the overseer clears steering — no injection, and develop/review/sync run from the spec and AGENTS.md as usual.

State (current phase, cycle, run history) lives in `.curious/state.json`. A durable Cursor agent (`agent-curious-<project>`) is created once and resumed on later runs.

### Python port (`python/`)

A parallel implementation lives under **`python/`**: same spec/state/harvest format, **local-first harness** (OpenAI-compatible HTTP to Ollama/vLLM by default; [LiteLLM](https://github.com/BerriAI/litellm) optional). CLI: `curious-py`. See [python/README.md](python/README.md).

## Install

One-time setup from this repo:

```bash
cd /path/to/curious
npm install
npm link
```

That puts `curious` on your PATH. Then from **any** project:

```bash
cd ~/projects/my-app
export CURSOR_API_KEY="cursor_..."
curious bootstrap
curious roadmap
curious run
```

### Other install options

```bash
npm install -g /path/to/curious
npm install -D github:theapemachine/curious   # then: npx curious bootstrap
npm install -g @theapemachine/curious         # after publishing
```

See [docs/publish.md](docs/publish.md) for npm pack verification and publish prerequisites (human-only).

After changing curious itself: `npm run build && npm link`.

## Quick start

```bash
cd your-project
export CURSOR_API_KEY="cursor_..."

curious bootstrap          # agent writes spec/SPEC.md
$EDITOR spec/SPEC.md       # you refine vision / requirements

curious roadmap            # agent adds Roadmap + Progress
curious run                # T1.1, T1.2, … until roadmap complete
```

Run commands from the **project root** — the directory that contains `spec/SPEC.md`:

```text
my-project/
  README.md
  AGENTS.md              # optional; inlined in develop/review/overseer prompts
  spec/SPEC.md           # living spec (required after bootstrap)
  curious.config.json    # optional
  .curious/state.json    # phase, cycle, history
  src/...
```

Optional: `CURIOUS_DISCOVER=parents` to search parent directories for a spec (off by default).

## Run modes

`curious run` defaults to **until done**: it stops when every `T*` / `M*` task in **## Roadmap** is checked (`[x]`). Progress is logged at startup and after each sync. Use only one mode flag per invocation.

| Mode                     | Command                    | Stops when                                                                 |
|--------------------------|----------------------------|----------------------------------------------------------------------------|
| **Until done** (default) | `curious run`              | All `T*` / `M*` tasks in **## Roadmap** are `[x]`                        |
| Continuous               | `curious run --continuous` | Ctrl+C, `maxCycles` in config, or a phase error (does not exit at roadmap completion) |
| One task                 | `curious run --cycle`      | One develop → review → sync round (alias for `--cycles 1`)                 |
| N tasks                  | `curious run --cycles 5`   | Five full rounds                                                           |
| Single phase             | `curious run --once`       | Current phase only (develop, review, sync, or overseer from state)         |

Examples:

```bash
curious run                 # full roadmap automation (default --until-done)
curious run --cycle         # one task, then exit (good for trying the loop)
curious run --cycles 3      # three tasks, then exit
curious run --continuous    # keep looping after roadmap complete (Ctrl+C to stop)
```

If the roadmap is already complete, default `curious run` exits immediately with `roadmap already complete`. Use `--continuous` for open-ended improvement (overseer may promote items from **## Next features** when the roadmap is fully checked).

### npm scripts (this repo)

```bash
npm run bootstrap
npm run roadmap
npm run run                 # until roadmap complete
npm run run:continuous      # until Ctrl+C
npm run run:cycle           # one task
npm run run:once            # single phase from state
npm run develop             # same as run:once when phase=develop in state
npm run review
npm run status
npm run inspect             # last failed run transcript
```

## Spec shape

After bootstrap and roadmap, `spec/SPEC.md` includes these sections (bootstrap schema order):

| Section                 | Purpose                                                                 |
|-------------------------|-------------------------------------------------------------------------|
| **Vision**              | Goals, constraints, and what exists today                               |
| **Requirements**        | `R1`, `R2`, … checkboxes                                                |
| **Roadmap**             | Phased tasks `T1.1`, `T1.2`, … (completion target for default `curious run`) |
| **Progress**            | Active tasks for the developer (sync maintains; often current phase only) |
| **Acceptance criteria** | Definition of done                                                      |
| **Orchestrator log**    | Cycle history; updated by sync                                          |
| **Constraints**         | Tech stack, style, workflow/git policy, non-goals                       |
| **Open questions**      | Unresolved decisions                                                    |

Dogfood and continuous-improvement specs may also include **## Next features** (backlog promoted into **Roadmap** when phases complete) and optional **## Agent steering** (overseer-only corrective bullets for develop/review/sync).

Task IDs in the roadmap use `T1.1` or `M0` style. The orchestrator only treats **## Roadmap** checkboxes with those IDs as completion criteria (not **Requirements**).

### Workflow (host + human commits)

Curious detects the machine it runs on (e.g. **arm64**) and injects a **Workflow** policy into every phase:

| Rule | Behavior |
|------|----------|
| **Commits** | **You** commit; agents never do. Review judges the **working tree** — uncommitted fixes are valid. |
| **Verification** | Tests on **this host only**. No GitHub Actions, CI URLs, or worktrees required. |
| **arm64** | `//go:build amd64` tests do not need to run; host tests + code review suffice for **5_verification** PASS. |
| **Steering** | Overseer may add steering; bullets demanding commit/CI/amd64 proof are stripped before injection. |
| **In doubt** | Read **file content** (`read`, `grep`, `git diff`) — not chat history, `HEAD`, or old reviews. |

Read-only **Git policy** still applies (no `reset`, `restore`, `commit`, `worktree`, etc.). For shell-level blocking, add hooks in the target repo.

Bootstrap seeds these constraints into new specs. **Edit your `spec/SPEC.md`** to soften acceptance criteria that still require amd64 CI or “branch tip == HEAD” if the overseer added them.

## Commands

| Command                         | Description                                  |
|---------------------------------|----------------------------------------------|
| `curious bootstrap [--verbose]` | Generate `spec/SPEC.md` from the project     |
| `curious roadmap [--verbose]`   | Add **Roadmap** + **Progress** from the spec |
| `curious run [options]`         | Develop → review → sync loop (see run modes) |
| `curious status`                | Print config paths and `.curious/state.json` |
| `curious reset`                 | Reset orchestrator state                     |
| `curious inspect [runId]`       | Inspect a run: header (phase/cycle/lastError), hints, transcript for `error`/`cancelled`, or `run.result` when finished |
| `curious harvest [--format dpo]` | Export fine-tuning JSONL from `.curious/state.json` |
| `curious init [dir]`            | Create an empty spec template (no agent)     |
| `curious --help`                | CLI help                                     |

Common flags: `--verbose`, `--config path/to/curious.config.json`.

## Configuration

Optional `curious.config.json` at the project root (see `curious.config.example.json` in the curious repo). Values merge as **defaults → config file → environment variables**. Pass an alternate path with `--config path/to/curious.config.json`.

```json
{
  "cwd": ".",
  "runtime": "local",
  "cycleDelayMs": 0,
  "maxCycles": 0,
  "overseerEveryNCycles": 5,
  "overseerOnReviewFailStreak": 2,
  "settingSources": ["project"],
  "harvest": { "enabled": false, "output": ".curious/harvest/" }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cwd` | string | project root | Agent working directory (relative to project root or absolute). |
| `specPath` | string | `spec/SPEC.md` | Living spec path (relative to project root or absolute). |
| `runtime` | `"local"` \| `"cloud"` | `"local"` | SDK runtime. **Local** (default): agent uses `cwd` on this machine. **Cloud**: remote SDK run — requires `cloud.repos`; see [Cloud runtime](#cloud-runtime-experimental) below. |
| `cycleDelayMs` | number | `0` | Pause between completed develop→review→sync cycles (ms). |
| `maxCycles` | number | `0` | Stop after N full rounds (`0` = unlimited). |
| `overseerEveryNCycles` | number | `5` | Run overseer after every N completed task cycles (`0` = off). |
| `overseerOnReviewFailStreak` | number | `2` | Run overseer after N consecutive review FAILs (`0` = off). |
| `settingSources` | string[] | `["project"]` | Cursor settings sources: `project`, `user`, `team`, `mdm`, `plugins`, `all`. |
| `agentId` | string | `agent-curious-<slug>` | Stable agent id for resume across runs. |
| `agentName` | string | `curious-<slug>` | Name when creating the Cursor agent. |
| `apiKey` | string | — | Optional API key; prefer `CURSOR_API_KEY` env. Do not commit secrets. |
| `model` | object | `composer-2.5` | **Ignored** — model is fixed at `composer-2.5`. |
| `cloud.repos` | `{ url, startingRef? }[]` | — | **Required for cloud runtime.** Git repo URLs; optional ref per repo. |
| `cloud.autoCreatePR` | boolean | `false` | Cloud runtime: open PR when run completes. |
| `cloud.skipReviewerRequest` | boolean | `true` | Cloud runtime: skip reviewer request on PRs. |
| `cloud.workOnCurrentBranch` | boolean | `false` | Cloud runtime: use current branch instead of a new branch. |
| `harvest.enabled` | boolean | `false` | Opt-in flag for harvest tooling; CLI `curious harvest` still works when invoked. |
| `harvest.output` | string | `.curious/harvest/` | Default output file or directory for harvest exports. |

All agent runs use **Composer 2.5** (`composer-2.5`). The model cannot be overridden via config or env.

## Cloud runtime (experimental)

Curious supports two SDK runtimes via `runtime` in config (or `CURIOUS_RUNTIME`):

| Runtime | Config | Where the agent runs |
|---------|--------|----------------------|
| **`local`** (default) | `cwd`, `settingSources` | Your machine — project directory on disk |
| **`cloud`** | `cloud.repos` (+ optional PR flags) | Cursor cloud against the listed Git remote(s) |

**Supported today (config → SDK wiring):**

- `buildAgentOptions` in `src/agent.ts` maps `runtime: "local"` to `options.local` (`cwd`, `settingSources`) and `runtime: "cloud"` to `options.cloud` (`repos`, `autoCreatePR`, `skipReviewerRequest`, `workOnCurrentBranch`).
- The same develop → review → sync → overseer loop runs for both; orchestrator logs `(local)` or `(cloud)` at connect time.
- `CURIOUS_RUNTIME=cloud` switches runtime; **`cloud.*` fields must be in `curious.config.json`** (no env override for `cloud`).

**Local-only orchestrator behavior:**

- Stuck-run recovery (`send` with `local.force`) applies only when `runtime === "local"`.
- Connection-guard retries and `needsForceNextSend` recovery are tuned for local runs.
- Workflow policy still injects host-only verification — cloud agents operate on the remote repo; reviews may not match local-host assumptions.

**Not validated in this repository:**

- Dogfood (`curious run` on this repo), `docs/smoke-test.md`, and unit tests assume **`runtime: "local"`**.
- Cloud has **no automated regression tests** here; treat as experimental SDK passthrough until you verify on your target repo.

**Example cloud config** (copy `cloud` block into `curious.config.json`; remove or ignore when using local):

```json
{
  "runtime": "cloud",
  "cloud": {
    "repos": [{ "url": "https://github.com/org/your-repo", "startingRef": "main" }],
    "autoCreatePR": false,
    "skipReviewerRequest": true,
    "workOnCurrentBranch": false
  }
}
```

Or: `export CURIOUS_RUNTIME=cloud` with `cloud` in the config file.

**Startup errors:**

- `Cloud runtime requires curious.config.json cloud.repos.` — set `runtime` back to `local`, or add a non-empty `cloud.repos` array.

**Non-goals (v0.1):** Cloud is not the primary Curious workflow; no cloud-specific docs beyond this section, no cloud smoke checklist, and no guarantee that bootstrap/roadmap spec files on disk stay in sync with what the remote agent edits.

## Environment

| Variable                 | Config field | Effect                                           |
|--------------------------|--------------|--------------------------------------------------|
| `CURSOR_API_KEY`         | `apiKey`     | **Required** for agent runs (env preferred)      |
| `CURIOUS_CWD`            | —            | Start directory for project discovery            |
| `CURIOUS_SPEC_PATH`      | `specPath`   | Override spec file path                          |
| `CURIOUS_DISCOVER`       | —            | Set to `parents` to walk up for `spec/SPEC.md`   |
| `CURIOUS_RUNTIME`        | `runtime`    | `local` or `cloud`                               |
| `CURIOUS_AGENT_ID`       | `agentId`    | Override stable agent id                         |
| `CURIOUS_CYCLE_DELAY_MS` | `cycleDelayMs` | Delay between cycles                           |
| `CURIOUS_MAX_CYCLES`     | `maxCycles`  | Max develop→review→sync rounds (`0` = unlimited) |
| `CURIOUS_OVERSEER_EVERY_N_CYCLES` | `overseerEveryNCycles` | Overseer interval (`0` = disable) |
| `CURIOUS_OVERSEER_FAIL_STREAK` | `overseerOnReviewFailStreak` | Overseer after N review FAILs (`0` = disable) |

No env overrides exist for `agentName`, `settingSources`, `cloud`, or `harvest` — set those in `curious.config.json`.

## Troubleshooting

- **Stopped after one task** — You likely used `--cycle`. Use `curious run` (no flags) for the full roadmap.
- **Phase stuck after error** — Fix the issue, then re-run; the orchestrator stays on the failed phase until a run finishes successfully.
- **No AGENTS.md** — Develop/review still run; a warning is printed. Add `AGENTS.md` at the project root or agent `cwd` for style rules.
- **Failed run details** — on ERROR during a phase, curious prints `[curious] error reason: …` and a conversation tail. `curious inspect` (or `curious inspect <runId>`) shows phase/cycle/lastError, actionable hints (missing API key, transient errors, etc.), and the full error transcript only for `error`/`cancelled` runs; finished runs print `run.result` when present. Use `curious run --verbose` for live streaming.
- **`ECONNRESET` / connection dropped** — curious retries the same phase after 10s instead of exiting.
- **`already has active run`** — a prior run was left wedged (often after a crash). Curious retries with `force` to expire it; rebuild curious if you still see `retryable=false` and the process exits.
- **`ECONNRESET` loop on review** — curious retries with backoff (15s → 30s → …), reconnects the agent after 3 drops, and stops after 12 failures per phase so you can re-run `curious run` instead of crashing.
- **Agent discarded uncommitted work via git** — review should FAIL **6_git_safety**. Re-run develop; do not use `git reset`/`restore` yourself unless you intend to.
- **Review FAIL for “not committed” or “no amd64 output” on arm64** — rebuild curious; workflow policy treats those as non-blocking. Trim the same requirements from **Acceptance criteria** in your spec if needed.
- **Cloud runtime errors** — `cloud.repos` is required when `runtime` is `cloud`; `settingSources` and `cwd` apply to **local** only. Stuck-run `force` recovery does not run in cloud mode. See [Cloud runtime](#cloud-runtime-experimental).

## License

MIT
