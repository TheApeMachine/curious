# curious-py

Python port of **curious** — spec-driven **develop → review → sync** loop with a **minimal custom harness**.

**Local-first:** default provider talks to any **OpenAI-compatible HTTP API** (Ollama, vLLM, llama.cpp) using only the Python stdlib — no LiteLLM required.

Shares `.curious/state.json` and `spec/SPEC.md` with the TypeScript CLI.

## Install

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
# Hugging Face stack (pick what you need):
pip install -e '.[transformers]'   # Transformers weights, native tool loop
pip install -e '.[smolagents]'     # smolagents agent + TransformersModel
pip install -e '.[train]'          # TRL DPO + PEFT LoRA
pip install -e '.[litellm]'        # optional hosted APIs
pip install -e '.[all]'            # everything
```

## MacBook Pro M4 Max (128GB unified, ~96GB for models)

Your machine is in the **“run the best local coding agent comfortably”** tier. You do **not** need cloud or LiteLLM for daily `curious-py` runs.

| Pick | Ollama | RAM (typical) | Why |
|------|--------|---------------|-----|
| **Primary (recommended)** | `qwen3-coder:30b` | ~20–35GB + context | Best tool-calling on Ollama; MoE stays fast |
| **Alternative** | `devstral-small-2:24b` | ~15–25GB + context | 24B dense, strong SWE-style coding |
| **Higher raw quality** | `qwen2.5-coder:32b` | ~30–40GB at Q8 | Older but still excellent; more RAM than Qwen3-Coder-30B |
| **Not local** | `qwen3-coder:480b` | ~250GB+ | Use `:480b-cloud` only — won’t fit in 96GB |

**Context:** Agent prompts (spec + AGENTS.md + history) need a large window. Before `ollama serve`:

```bash
export OLLAMA_CONTEXT_LENGTH=65536   # or 32768 if you hit memory pressure
```

**Quantization:** With ~96GB headroom, prefer **Q8** (or Ollama’s default quality) for the 30B class — avoid over-quantizing to Q4 unless you want speed over quality.

**After fine-tuning:** Serve your adapter with **MLX** or **llama.cpp** OpenAI-compatible server, or merge LoRA and run via Ollama — keep `provider: openai_compat`.

## Local model (default)

1. Start a local server, e.g. [Ollama](https://ollama.com):

```bash
ollama pull qwen3-coder:30b
ollama serve
```

2. Configure (defaults match Ollama):

```json
{
  "llm": {
    "provider": "openai_compat",
    "model": "qwen3-coder:30b",
    "baseUrl": "http://127.0.0.1:11434/v1",
    "apiKey": "local"
  }
}
```

Or env only:

```bash
export LLM_MODEL=qwen3-coder:30b
export LLM_BASE_URL=http://127.0.0.1:11434/v1
```

3. Run:

```bash
curious-py bootstrap
curious-py run --cycle
```

After fine-tuning, serve your adapter with **vLLM** (or Ollama) and point `baseUrl` at that server — same `openai_compat` provider.

## LLM providers (`llm.provider`)

| Provider | Library | Install | `model` field |
|----------|---------|---------|---------------|
| **`openai_compat`** | stdlib HTTP | core | Ollama tag, e.g. `qwen3-coder:30b` |

**Ollama not running?** With `pip install 'curious-py[transformers]'`, the default config auto-falls back to in-process Transformers and downloads `fallbackModel` (default `Qwen/Qwen3-Coder-30B-A3B-Instruct`) from Hugging Face when `http://127.0.0.1:11434` refuses connections. Set `llm.fallbackToTransformers: false` to disable.
| **`transformers`** | [Transformers](https://huggingface.co/docs/transformers/index) | `[transformers]` | HF repo id |
| **`smolagents`** | [smolagents](https://huggingface.co/docs/smolagents/index) | `[smolagents]` | HF repo id |
| **`litellm`** | LiteLLM | `[litellm]` | e.g. `openai/gpt-5.5` |

### M4 Max — native Hugging Face (no Ollama)

```json
{
  "llm": {
    "provider": "smolagents",
    "model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    "device": "auto",
    "smolagentsAgentType": "tool-calling"
  }
}
```

### Hub + training

| Command | Library |
|---------|---------|
| `curious-py hf download …` | [huggingface_hub](https://huggingface.co/docs/huggingface_hub/index) |
| `curious-py train dpo` | [TRL](https://huggingface.co/docs/trl/index) + [PEFT](https://huggingface.co/docs/peft/index) |

```bash
pip install -e '.[smolagents,train]'
curious-py hf download Qwen/Qwen3-Coder-30B-A3B-Instruct -o ./models/qwen3-coder-30b
curious-py run --cycle
curious-py harvest --format dpo
curious-py train dpo --model Qwen/Qwen3-Coder-30B-A3B-Instruct
```

## Commands

```bash
curious-py init | bootstrap | roadmap | run [--cycle] | status | reset | harvest | train dpo | hf
```

## Harness tools

| Tool | Purpose |
|------|---------|
| `run_command` | Shell; **blocks mutating git** |
| `read_file` | Read with line range |
| `write_file` | Create/overwrite |
| `search_replace` | Unique replace |

## Model picks (checked May 2026)

Sources: [Ollama coding models blog](https://ollama.com/blog/coding-models), [OpenHands local LLMs](https://docs.openhands.dev/openhands/usage/llms/local-llms), [HF BigCodeBench](https://huggingface.co/spaces/bigcode/bigcodebench-leaderboard).

| Tier | Model | Ollama tag / HF id | Notes |
|------|--------|-------------------|--------|
| **Best local agent (12–24GB)** | Qwen3-Coder 30B A3B | `qwen3-coder:30b` / `Qwen/Qwen3-Coder-30B-A3B-Instruct` | MoE (~3.3B active), tool calling, 256K ctx; Ollama’s default coding pick |
| **Alternative local agent** | Devstral Small 2 | `devstral-small-2` / `mistralai/Devstral-Small-2-24B-Instruct-2512` | 24B dense, strong SWE-bench, vision |
| **Fine-tune → agent** | OpenHands LM 32B | HF only / serve via vLLM | `OpenHands/openhands-lm-32b-v0.1` — agent-tuned on Qwen2.5-Coder 32B |
| **Lighter GPU (8–16GB)** | Qwen2.5-Coder 7B–14B | `qwen2.5-coder:7b` etc. | Still strong; less SWE-bench than Qwen3-Coder |
| **Heavy local (64GB+)** | Qwen3-Coder 480B | `qwen3-coder:480b` | Needs ~300GB+ VRAM per Ollama |
| **Cloud (no local GPU)** | GLM-4.6 / Qwen3-Coder 480B | `glm-4.6:cloud`, `qwen3-coder:480b-cloud` | Via Ollama cloud + same `openai_compat` endpoint |

**Stale hosted defaults to avoid:** `gpt-4o`, `claude-sonnet-4-5-20250929`, bare `qwen3-coder` (use `qwen3-coder:30b` on Ollama).

**For curious-py after fine-tuning:** train on HF weights → serve with **vLLM** (tool calling) → keep `provider: openai_compat` and set `baseUrl` to your server.

## Tests

```bash
pytest
```
