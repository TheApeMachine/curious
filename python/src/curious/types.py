from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Phase = Literal["develop", "review", "sync", "overseer"]
RunStatus = Literal["finished", "error", "cancelled"]

# How the agent loop talks to a model
LlmProvider = Literal[
    "openai_compat",  # Ollama, vLLM, any /v1/chat/completions (stdlib HTTP)
    "litellm",  # optional: pip install curious-py[litellm]
    "transformers",  # optional: pip install curious-py[transformers] — native loop + HF weights
    "smolagents",  # optional: pip install curious-py[smolagents] — HF smolagents agent
]

SmolagentsAgentType = Literal["tool-calling", "code"]


@dataclass
class LlmConfig:
    """Model routing. See python/README.md for provider matrix."""

    provider: LlmProvider = "openai_compat"
    model: str = "qwen3-coder:30b"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 16384
    temperature: float = 0.2
    timeout_sec: int = 600
    # Hugging Face local (transformers / smolagents)
    device: str | None = None  # mps, cuda, cpu, auto
    load_in_4bit: bool = False
    trust_remote_code: bool = True
    smolagents_agent_type: SmolagentsAgentType = "tool-calling"


@dataclass
class HarnessConfig:
    max_turns: int = 80
    command_timeout_sec: int = 300


@dataclass
class HarvestConfig:
    enabled: bool = False
    output: str = ".curious/harvest/"


@dataclass
class TrainConfig:
    """Defaults for `curious-py train dpo` (TRL + PEFT)."""

    output_dir: str = ".curious/train/dpo"
    lora_r: int = 16
    lora_alpha: int = 32
    learning_rate: float = 5e-6
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 4
    max_length: int = 4096
    max_prompt_length: int = 2048


@dataclass
class CuriousConfig:
    spec_path: str
    cwd: str
    llm: LlmConfig
    harness: HarnessConfig = field(default_factory=HarnessConfig)
    """Git branch Curious checks out before agent work (default: curious)."""
    agent_branch: str = "curious"
    ensure_agent_branch: bool = True
    cycle_delay_ms: int = 0
    max_cycles: int = 0
    overseer_every_n_cycles: int = 5
    overseer_on_review_fail_streak: int = 2
    harvest: HarvestConfig | None = None
    train: TrainConfig | None = None


@dataclass
class CycleRecord:
    cycle: int
    phase: Phase
    run_id: str
    status: RunStatus
    started_at: str
    finished_at: str
    summary: str | None = None


@dataclass
class CuriousState:
    version: int = 1
    phase: Phase = "develop"
    cycle: int = 0
    running: bool = False
    last_run_id: str | None = None
    last_error: str | None = None
    history: list[CycleRecord] = field(default_factory=list)
    updated_at: str = ""

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "phase": self.phase,
            "cycle": self.cycle,
            "running": self.running,
            "lastRunId": self.last_run_id,
            "lastError": self.last_error,
            "history": [
                {
                    "cycle": r.cycle,
                    "phase": r.phase,
                    "runId": r.run_id,
                    "status": r.status,
                    "startedAt": r.started_at,
                    "finishedAt": r.finished_at,
                    **({"summary": r.summary} if r.summary else {}),
                }
                for r in self.history
            ],
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_json(cls, data: dict) -> CuriousState:
        history = []
        for item in data.get("history", []):
            history.append(
                CycleRecord(
                    cycle=item["cycle"],
                    phase=item["phase"],
                    run_id=item["runId"],
                    status=item["status"],
                    started_at=item["startedAt"],
                    finished_at=item["finishedAt"],
                    summary=item.get("summary"),
                )
            )
        return cls(
            version=data.get("version", 1),
            phase=data.get("phase", "develop"),
            cycle=data.get("cycle", 0),
            running=data.get("running", False),
            last_run_id=data.get("lastRunId"),
            last_error=data.get("lastError"),
            history=history,
            updated_at=data.get("updatedAt", ""),
        )


@dataclass
class ResolvedConfig(CuriousConfig):
    project_root: str = ""
    has_spec: bool = False
