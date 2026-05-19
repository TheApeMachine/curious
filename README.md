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
| **overseer** | Overseer | Meta-review: failure patterns, spec alignment; may edit Roadmap/Progress; **optionally** adds **Agent steering** when something needs correction; no code |

After **sync** completes a task cycle, **overseer** may run before the next **develop** when:

- Every **N** completed task cycles (`overseerEveryNCycles`, default **5**), or
- **2** consecutive **review** FAILs (`overseerOnReviewFailStreak`, default **2**)

Set either interval to `0` in `curious.config.json` to disable that trigger.

### Agent steering (optional, exception-only)

When the overseer finds **concrete** problems (repeated review FAILs, drift, wrong focus), it may add **`## Agent steering`** to the spec with `### Developer`, `### Reviewer`, and/or `### Sync` bullets. Curious injects only **actionable** bullets into that phase’s prompt (above AGENTS.md).

When the team is healthy, the overseer leaves steering empty or clears it — **no injection**, and develop/review/sync run from the spec and AGENTS.md as usual. Steering is the exception, not a standing requirement.

State (current phase, cycle, run history) lives in `.curious/state.json`. A durable Cursor agent (`agent-curious-<project>`) is created once and resumed on later runs.

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

`curious run` defaults to **until done**: it stops when every task in **## Roadmap** is checked (`- [x] T1.1`, `- [x] M0`, …). Progress is logged at startup and after each sync.

| Mode                     | Command                    | Stops when                                        |
|--------------------------|----------------------------|---------------------------------------------------|
| **Until done** (default) | `curious run`              | All `T*` / `M*` tasks in **## Roadmap** are `[x]` |
| Continuous               | `curious run --continuous` | You press Ctrl+C (ignores roadmap completion)     |
| One task                 | `curious run --cycle`      | One develop → review → sync round                 |
| N tasks                  | `curious run --cycles 5`   | Five full rounds                                  |
| Single phase             | `curious run --once`       | Current phase only (develop, review, sync, or overseer) |

Examples:

```bash
curious run                 # full roadmap automation
curious run --cycle         # one task, then exit (good for trying the loop)
curious run --cycles 3      # three tasks, then exit
curious run --continuous    # keep running after roadmap (manual stop)
```

If the roadmap is already complete, `curious run` exits immediately with `roadmap already complete`.

### npm scripts (this repo)

```bash
npm run bootstrap
npm run roadmap
npm run run                 # until roadmap complete
npm run run:continuous      # until Ctrl+C
npm run run:cycle           # one task
npm run develop             # one develop phase (same as run --once when phase=develop)
npm run review
npm run status
npm run inspect             # last failed run transcript
```

## Spec shape

After bootstrap and roadmap, `spec/SPEC.md` typically includes:

| Section                 | Purpose                                                              |
|-------------------------|----------------------------------------------------------------------|
| **Vision**              | Goals and constraints                                                |
| **Requirements**        | `R1`, `R2`, … checkboxes                                             |
| **Roadmap**             | Phased tasks `T1.1`, `T1.2`, … (completion target for `curious run`) |
| **Progress**            | Active tasks for the developer (often current phase only)            |
| **Orchestrator log**    | Cycle history; updated by sync                                       |
| **Acceptance criteria** | Definition of done                                                   |

Task IDs in the roadmap use `T1.1` or `M0` style. The orchestrator only treats **## Roadmap** checkboxes with those IDs as completion criteria (not **Requirements**).

### Git policy (all agents)

Every phase prompt includes a **binding** read-only git rule: agents may use `git status`, `git diff`, `git log`, `git show`, and similar read commands only. They must **not** run mutating git (`reset`, `restore`, `checkout`/`switch` to discard work, `clean`, `stash`, `commit`, `rebase`, etc.). The reviewer scores **6_git_safety** and fails the run if develop used mutating git.

This is enforced in prompts (the Cursor SDK does not offer a shell denylist). For stronger protection in a target repo, add the same rule to **AGENTS.md** or a Cursor rule, and use [hooks](https://cursor.com/docs/agent/hooks) to block mutating `git` in the shell if needed.

Bootstrap seeds the constraint into **## Constraints** in new specs.

## Commands

| Command                         | Description                                  |
|---------------------------------|----------------------------------------------|
| `curious bootstrap [--verbose]` | Generate `spec/SPEC.md` from the project     |
| `curious roadmap [--verbose]`   | Add **Roadmap** + **Progress** from the spec |
| `curious run [options]`         | Develop → review → sync loop (see run modes) |
| `curious status`                | Print config paths and `.curious/state.json` |
| `curious reset`                 | Reset orchestrator state                     |
| `curious inspect [runId]`       | Show transcript for a failed run             |
| `curious init [dir]`            | Create an empty spec template (no agent)     |
| `curious --help`                | CLI help                                     |

Common flags: `--verbose`, `--config path/to/curious.config.json`.

## Configuration

Optional `curious.config.json` at the project root:

```json
{
  "cwd": ".",
  "runtime": "local",
  "cycleDelayMs": 0,
  "maxCycles": 0,
  "overseerEveryNCycles": 5,
  "overseerOnReviewFailStreak": 2,
  "settingSources": ["project"]
}
```

| Field                      | Description                                                                         |
|----------------------------|-------------------------------------------------------------------------------------|
| `cwd`                      | Agent working directory (relative to project root). Spec stays at `./spec/SPEC.md`. |
| `runtime`                  | `local` or `cloud`                                                                  |
| `cycleDelayMs`             | Pause between completed cycles in ms (default `0`)                                  |
| `maxCycles`                | Stop after N full rounds (`0` = no limit)                                           |
| `overseerEveryNCycles`     | Run overseer after every N completed task cycles (`0` = off)                        |
| `overseerOnReviewFailStreak` | Run overseer after N consecutive review FAILs (`0` = off)                         |
| `settingSources`           | Cursor settings to load (e.g. project MCP, agents)                                  |
| `agentId`                  | Stable agent id (auto-derived from project name if omitted)                         |

All agent runs use **Composer 2.5** (`composer-2.5`). The model is fixed and cannot be overridden via config or env.

## Environment

| Variable                 | Effect                                           |
|--------------------------|--------------------------------------------------|
| `CURSOR_API_KEY`         | **Required** for agent runs                      |
| `CURIOUS_CWD`            | Start directory for project discovery            |
| `CURIOUS_SPEC_PATH`      | Override spec file path                          |
| `CURIOUS_DISCOVER`       | Set to `parents` to walk up for `spec/SPEC.md`   |
| `CURIOUS_RUNTIME`        | `local` or `cloud`                               |
| `CURIOUS_AGENT_ID`       | Override stable agent id                         |
| `CURIOUS_CYCLE_DELAY_MS` | Delay between cycles                             |
| `CURIOUS_MAX_CYCLES`     | Max develop→review→sync rounds (`0` = unlimited) |
| `CURIOUS_OVERSEER_EVERY_N_CYCLES` | Overseer interval (`0` = disable) |
| `CURIOUS_OVERSEER_FAIL_STREAK` | Overseer after N review FAILs (`0` = disable) |

## Troubleshooting

- **Stopped after one task** — You likely used `--cycle`. Use `curious run` (no flags) for the full roadmap.
- **Phase stuck after error** — Fix the issue, then re-run; the orchestrator stays on the failed phase until a run finishes successfully.
- **No AGENTS.md** — Develop/review still run; a warning is printed. Add `AGENTS.md` at the project root or agent `cwd` for style rules.
- **Failed run details** — on ERROR, curious prints `[curious] error reason: …` (first line of `run.result`), then a conversation tail with real tool names. Use `curious inspect` or `curious run --verbose`.
- **`ECONNRESET` / connection dropped** — curious retries the same phase after 10s instead of exiting.
- **`already has active run`** — a prior run was left wedged (often after a crash). Curious retries with `force` to expire it; rebuild curious if you still see `retryable=false` and the process exits.
- **`ECONNRESET` loop on review** — curious retries with backoff (15s → 30s → …), reconnects the agent after 3 drops, and stops after 12 failures per phase so you can re-run `curious run` instead of crashing.
- **Agent discarded uncommitted work via git** — review should FAIL **6_git_safety**. Re-run develop; do not use `git reset`/`restore` yourself unless you intend to. Consider a shell hook in the project to hard-block mutating git for agents.

## License

MIT
