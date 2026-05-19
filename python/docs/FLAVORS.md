# Curious flavors (Python)

## Models (May 2026)

| Role | Default HF id |
|------|----------------|
| Develop | `Qwen/Qwen3-Coder-Next` |
| Verifier | `Qwen/Qwen3-1.7B` |
| Fallback (no Ollama) | `Qwen/Qwen3-Coder-Next` |

## Phase 0 — Trajectories

- `CycleRecord.trajectory`: tool calls with 2KB result excerpts (50KB cap per cycle)
- `spec_snapshot_sha` / `agents_snapshot_sha` per phase
- State version 2 (v1 records load with empty trajectory)

## Phase 1 — Spec versioning & scanner

- `.curious/spec_history/{cycle:04d}-{phase}.md`
- `curious-py spec-history correlate`
- `.curious/scanner_rules.json` from overseer diffs
- Reviewer prompt gets deterministic scanner violations

## Phase 2 — Verifier & best-of-N

```bash
curious-py harvest --format verifier
curious-py train verifier
```

Enable in config:

```json
"verifier": { "enabled": true, "baseModel": "Qwen/Qwen3-1.7B" },
"harness": { "bestOfN": { "enabled": true, "n": 4 } }
```

Disagreements → `.curious/verifier_disagreement.jsonl`

## Phase 3 — Trajectory DPO & GRPO

```bash
curious-py harvest --format dpo   # includes tool trajectories
curious-py train dpo
curious-py train grpo             # scaffold + tasks.jsonl from roadmap
```

## Phase 4 — Split models & reviewer harvest

```json
"reviewLlm": { "provider": "transformers", "model": "Qwen/Qwen3-1.7B" },
"overseerLlm": null
```

```bash
curious-py harvest --format reviewer
```
