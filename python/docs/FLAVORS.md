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
curious-py harvest --format dpo      # tool trajectories in chosen/rejected
curious-py harvest --format grpo     # develop prompts from roadmap + history
curious-py train verifier            # optional but used in GRPO reward
curious-py train grpo --rollouts 4   # TRL GRPOTrainer + composite reward
curious-py train dpo                 # DPO on trajectory-formatted pairs
```

GRPO reward = `0.65 × verifier + 0.25 × heuristics − scanner penalties` (see `train/grpo_reward.py`).

After GRPO, set `llm.adapterPath` to `.curious/train/grpo` and `llm.provider` to `transformers`.

### Remote training (Vast.ai)

All `curious-py train …` commands support automatic Vast.ai execution when `VAST_API_KEY` is set: cheapest matching GPU, interruptible spot bid, bundle upload, remote `--local` train, artifact sync to `.curious/train`, instance teardown. Use `--local` / `--vast` to override. See [python/README.md](../README.md#vastai-automatic-cost-optimized-gpu-training).

## Phase 4 — Split models & reviewer harvest

```json
"reviewLlm": { "provider": "transformers", "model": "Qwen/Qwen3-1.7B" },
"overseerLlm": null
```

```bash
curious-py harvest --format reviewer
```
