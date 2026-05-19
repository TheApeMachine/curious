# Curious backlog

Tracked follow-ups from design review (May 2026).

## Done / in progress

| Item | Status | Notes |
|------|--------|-------|
| Vast `gpu_name in [...]` query DSL | **fixed** | Comma-separated names per Vast search syntax |
| Harvest uses current `git diff` for all historical reviews | **fixed** | `CycleRecord.diff_at_review` captured at review end |
| `state.py` v1→v2 dead branch in `from_json` | **fixed** | `load_state` owns version bump |
| `harvest/__init__.py` output path ternary | **fixed** | Clear `.jsonl` vs directory rules |
| GRPO verifier train/eval mismatch | **mitigated** | Verifier weight only when completion looks like a unified diff |
| Bootstrap exits without writing `spec/SPEC.md` (transformers) | **fixed** | Required-path nudge in harness; spec validation; tool prompt fallback for HF |

## Open — observability

- Cycle trace visualization / replay from `state.json` + spec snapshots
- Dashboard: phase timeline, tool calls, verdict parse failures
- One-command replay of cycle N in dry-run

## Open — memory & spec metrics

- Semantic retrieval over past failures / trajectories
- Spec evolution metrics: roadmap churn, overseer intervention rate, task volatility
- Recurring bug pattern clustering across repos

## Open — reviewers

- Specialized reviewers: security, performance, architecture, test adequacy
- Same `review-verdict` contract, criterion-specific prompts

## Open — training

- **GRPO + real diffs**: run tool rollouts in a worktree, `git diff` that tree, score with verifier (matches verifier harvest distribution)
- Alternative: train a separate verifier head on prose+tool-call proxy
- Multi-agent disagreement log → reviewer calibration / uncertainty-aware orchestration

## Open — execution

- Docker-per-task / ephemeral VM sandboxes for cleaner pass/fail labels
- Filesystem snapshots + deterministic replay for harvest

## Ops — next experiments

- **First Vast trial**: `curious-py train verifier --vast` (cheapest profile)
- **Harvest on caramba**: after a develop/review cycle run, `curious-py harvest --format verifier`
