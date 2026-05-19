# Curious smoke test — manual checklist

End-to-end manual verification that **Curious** works on a **fresh sample project**: `bootstrap` → `roadmap` → `run --cycle`. Use this after installing or changing the CLI, or before dogfooding a release.

This checklist exercises **R1** (CLI commands and run modes) and **R3** (bootstrap/roadmap agents write `spec/SPEC.md` without editing product source). It does **not** require running the full roadmap — one develop → review → sync round is enough.

## Prerequisites

Before starting, confirm:

- [ ] **Node.js ≥ 18** — `node --version`
- [ ] **Curious CLI on PATH** — from the curious repo: `npm install && npm run build && npm link`
- [ ] **`CURSOR_API_KEY` set** — `echo "${CURSOR_API_KEY:+set}"` prints `set` (never paste the key into logs)
- [ ] **CLI help works** — `curious --help` exits 0 and lists `bootstrap`, `roadmap`, `run`
- [ ] **Network access** — agent runs call the Cursor SDK (local runtime)

Optional: run `npm test` in the curious repo first to confirm the host harness passes (164+ tests on a healthy tree).

## Prepare a fresh sample project

Use a **new empty directory** — not the curious dogfood repo. The sample should have enough context for bootstrap to infer vision and requirements, but **no** `spec/SPEC.md` yet.

```bash
SMOKE_DIR="$(mktemp -d)"
cd "$SMOKE_DIR"
echo "Sample project: $SMOKE_DIR"
```

Create a minimal project (copy-paste as one block):

```bash
cat > README.md <<'EOF'
# tiny-counter

Minimal Node.js counter library for smoke-testing Curious.

## Usage

Increment a counter and read the value.

## Goals

- Single-file implementation in `src/counter.js`
- One co-located test file using `node:test`
EOF

mkdir -p src
cat > src/counter.js <<'EOF'
let n = 0;
export function increment() { return ++n; }
export function value() { return n; }
export function reset() { n = 0; }
EOF

cat > package.json <<'EOF'
{
  "name": "tiny-counter",
  "type": "module",
  "version": "0.0.1",
  "private": true
}
EOF
```

Verify the starting state:

- [ ] `README.md` exists at project root
- [ ] `spec/SPEC.md` does **not** exist yet (`test ! -f spec/SPEC.md`)
- [ ] `.curious/state.json` does **not** exist yet
- [ ] Current directory is the project root (`pwd` equals `$SMOKE_DIR`)

## Step 1 — `curious bootstrap`

From the sample project root:

```bash
export CURSOR_API_KEY="cursor_..."   # if not already in the environment
curious bootstrap --verbose
```

**Expected while running**

- [ ] CLI prints that it will create `spec/SPEC.md` (or refine if re-run)
- [ ] Agent explores README and code; run finishes with status **finished** (exit 0)
- [ ] Printed next steps mention `curious roadmap` and `curious run --cycle`

**Expected on disk**

- [ ] `spec/SPEC.md` exists and is non-empty
- [ ] Spec includes required sections: **Vision**, **Requirements**, **Roadmap**, **Progress**, **Acceptance criteria**, **Orchestrator log**, **Constraints**, **Open questions**
- [ ] **Requirements** use checkbox form (`- [ ] R1: …`)
- [ ] **Roadmap** has phased tasks with IDs (`T1.1`, `T1.2`, …)
- [ ] Bootstrap did **not** modify `src/counter.js` or other product source (only spec was written)

**Optional human step**

- [ ] Skim `spec/SPEC.md` and adjust Vision/Requirements if bootstrap misread the sample (not required for smoke pass)

Record bootstrap outcome:

| Field | Value |
|-------|-------|
| Exit code | |
| Spec path | `spec/SPEC.md` |
| First roadmap task ID | e.g. `T1.1` |

## Step 2 — `curious roadmap`

Still from the sample project root:

```bash
curious roadmap --verbose
```

**Expected while running**

- [ ] CLI reads existing `spec/SPEC.md` (requires spec from step 1)
- [ ] Agent run finishes with status **finished** (exit 0)
- [ ] Printed next steps mention `curious run --cycle`

**Expected on disk**

- [ ] **Roadmap** lists concrete phased tasks (`T*.*` IDs) tied to requirements
- [ ] **Progress** lists at least one unchecked task (`- [ ] T…`)
- [ ] **Progress** focuses on the current phase (typically first phase only)
- [ ] Roadmap/Progress tasks are implementable in one develop cycle each
- [ ] Still no changes to product source outside `spec/SPEC.md`

Quick parse check (optional):

```bash
grep -E '^- \[ \] T[0-9]+\.[0-9]+' spec/SPEC.md | head -3
```

- [ ] At least one unchecked `T*.*` line appears in **Progress**

## Step 3 — `curious run --cycle`

One full **develop → review → sync** round (alias for `--cycles 1`):

```bash
curious run --cycle --verbose
```

**Expected while running**

- [ ] Orchestrator logs phase transitions: **develop**, then **review**, then **sync**
- [ ] **Develop** implements exactly one unchecked **Progress** task (lowest ID first)
- [ ] **Review** emits a structured `review-verdict` block (six criteria + `OVERALL: PASS` or `FAIL`)
- [ ] **Sync** updates spec on **PASS** (checks off Roadmap/Progress, appends **Orchestrator log**); on **FAIL**, leaves tasks open and records blockers
- [ ] Process exits after one round (does not continue through the full roadmap)
- [ ] Exit code 0 when all three phases finish successfully

**Expected on disk after PASS**

- [ ] `.curious/state.json` exists with `phase`, `cycle`, and non-empty `history`
- [ ] History includes finished records for **develop**, **review**, and **sync** for the same cycle
- [ ] First **Progress** task is checked `[x]` in `spec/SPEC.md` (if review PASS)
- [ ] Matching **Roadmap** task is checked `[x]`
- [ ] **Orchestrator log** has a new row for the completed cycle
- [ ] Product changes from develop (if any) are in the **working tree** — agents do not commit; that is expected

**Expected on disk after review FAIL**

- [ ] Tasks remain unchecked in Roadmap/Progress
- [ ] **Orchestrator log** or sync notes record FAIL / blockers
- [ ] Re-run `curious run --cycle` to retry the same task (or fix blockers first)

Record cycle outcome:

| Field | Value |
|-------|-------|
| Exit code | |
| Active task ID | |
| Review OVERALL | PASS / FAIL |
| Cycle number (from status) | |

## Post-smoke verification

From the sample project root:

```bash
curious status
```

- [ ] `status` exits 0 and prints JSON with `config.projectRoot`, `config.specPath`, and `state.history`
- [ ] `state.phase` is a valid phase (`develop`, `review`, `sync`, or `overseer`)
- [ ] `state.history` length increased compared to before step 3

If any phase ended in **error**:

```bash
curious inspect
```

- [ ] Inspect prints phase/cycle/`lastError`, hints (e.g. missing API key, transient network), and transcript for failed runs

CLI smoke (no agent):

```bash
curious --help | grep -E 'bootstrap|roadmap|run'
```

- [ ] Help still lists core commands

## Pass criteria (summary)

Smoke **PASS** when all of the following hold:

1. **Bootstrap** created a valid `spec/SPEC.md` with the required section schema (**R3**).
2. **Roadmap** expanded **Roadmap** + **Progress** without editing product source (**R3**).
3. **`run --cycle`** completed one develop → review → sync round and exited (**R1**, **R5**).
4. **`.curious/state.json`** persists orchestrator state (**R2**).
5. On review **PASS**, sync checked off the first task in Roadmap and Progress.
6. No agent used mutating git commands (review **6_git_safety** should PASS when review PASS).

Smoke **FAIL** if bootstrap/roadmap skip spec sections, `run --cycle` exits before sync, or the CLI commands are missing from help.

## Cleanup

The sample directory is disposable:

```bash
cd /
rm -rf "$SMOKE_DIR"
unset SMOKE_DIR
```

To re-smoke without recreating files, `curious reset` clears orchestrator state in an existing project (does not delete the spec).

## Troubleshooting

See [README.md](../README.md#troubleshooting) for connection errors, `--cycle` vs full `run`, missing `AGENTS.md`, and arm64 verification policy.

Common smoke issues:

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `CURSOR_API_KEY` / auth errors | Key missing or invalid | Export key; re-run failed phase |
| Bootstrap exits non-zero | Agent error or cancel | `curious inspect`; re-run `bootstrap` |
| Stopped after one task when expecting full roadmap | Used `--cycle` intentionally | For full automation use `curious run` (no mode flag) |
| Review FAIL “not committed” on arm64 | Stale curious build | Rebuild curious: `npm run build && npm link` |
| Phase stuck after error | Prior run failed mid-phase | Fix issue; re-run — orchestrator resumes failed phase |

## Related verification (curious repo)

When changing Curious itself:

| Check | Command |
|-------|---------|
| Compile | `npm run build` |
| Types | `npm run typecheck` |
| Unit tests | `npm test` |
| CLI help | `node dist/index.js --help` |
| Dogfood one task | `curious run --cycle` from curious repo root (requires `CURSOR_API_KEY`) |

Automated dogfood smoke lives in `src/smoke.test.ts` (CLI help, status, orchestrator history on this host). This document is the **manual** counterpart for a **fresh external project**.
