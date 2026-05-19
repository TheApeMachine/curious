from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from curious.trajectory import ToolCallTrace

Phase = Literal["develop", "review", "sync", "overseer"]
RunStatus = Literal["finished", "error", "cancelled"]

LlmProvider = Literal[
    "openai_compat",
    "litellm",
    "transformers",
    "smolagents",
]

SmolagentsAgentType = Literal["tool-calling", "code"]
STATE_VERSION = 2

CRITERION_KEYS = (
    "1_maintainability",
    "2_correctness_performance",
    "3_spec_compliance",
    "4_homogeneity",
    "5_verification",
    "6_git_safety",
)


@dataclass
class LlmConfig:
    provider: LlmProvider = "openai_compat"
    model: str = "qwen3-coder:30b"
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 16384
    temperature: float = 0.2
    timeout_sec: int = 600
    device: str | None = None
    load_in_4bit: bool = False
    trust_remote_code: bool = True
    smolagents_agent_type: SmolagentsAgentType = "tool-calling"
    fallback_to_transformers: bool = True
    fallback_model: str | None = None
    adapter_path: str | None = None


@dataclass
class BestOfNConfig:
    enabled: bool = False
    n: int = 4
    temperatures: list[float] = field(default_factory=lambda: [0.2, 0.5, 0.7, 0.9])


@dataclass
class HarnessConfig:
    max_turns: int = 80
    command_timeout_sec: int = 300
    best_of_n: BestOfNConfig = field(default_factory=BestOfNConfig)


@dataclass
class VerifierConfig:
    enabled: bool = False
    model_path: str | None = None
    base_model: str = "Qwen/Qwen3-1.7B"
    pass_threshold: float = 0.7
    disagreement_log: str = ".curious/verifier_disagreement.jsonl"


@dataclass
class HarvestConfig:
    enabled: bool = False
    output: str = ".curious/harvest/"


@dataclass
class VastGpuProfile:
    min_gpu_ram_gb: float = 24.0
    min_cuda_major: int = 12
    max_dph: float = 2.0
    disk_gb: int = 80
    preferred_gpus: list[str] = field(
        default_factory=lambda: [
            "RTX_4090",
            "RTX_3090",
            "L40",
            "A6000",
        ]
    )


@dataclass
class VastConfig:
    enabled: bool = True
    api_key: str | None = None
    interruptible: bool = True
    max_dph: float = 1.5
    disk_gb: int | None = None
    image: str = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
    label_prefix: str = "curious-train"
    auto_destroy: bool = True
    ssh_timeout_sec: int = 600
    train_timeout_sec: int = 86_400
    profiles: dict[str, VastGpuProfile] = field(default_factory=dict)


@dataclass
class TrainConfig:
    output_dir: str = ".curious/train/dpo"
    lora_r: int = 16
    lora_alpha: int = 32
    learning_rate: float = 5e-6
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 4
    max_length: int = 4096
    max_prompt_length: int = 2048
    verifier_output_dir: str = ".curious/train/verifier"
    grpo_output_dir: str = ".curious/train/grpo"


@dataclass
class CuriousConfig:
    spec_path: str
    cwd: str
    llm: LlmConfig
    review_llm: LlmConfig | None = None
    overseer_llm: LlmConfig | None = None
    harness: HarnessConfig = field(default_factory=HarnessConfig)
    verifier: VerifierConfig = field(default_factory=VerifierConfig)
    agent_branch: str = "curious"
    ensure_agent_branch: bool = True
    cycle_delay_ms: int = 0
    max_cycles: int = 0
    overseer_every_n_cycles: int = 5
    overseer_on_review_fail_streak: int = 2
    harvest: HarvestConfig | None = None
    train: TrainConfig | None = None
    vast: VastConfig | None = None

    def llm_for_phase(self, phase: Phase) -> LlmConfig:
        if phase == "review" and self.review_llm is not None:
            return self.review_llm
        if phase == "overseer" and self.overseer_llm is not None:
            return self.overseer_llm
        return self.llm


@dataclass
class CycleRecord:
    cycle: int
    phase: Phase
    run_id: str
    status: RunStatus
    started_at: str
    finished_at: str
    summary: str | None = None
    trajectory: list[ToolCallTrace] = field(default_factory=list)
    spec_snapshot_sha: str | None = None
    agents_snapshot_sha: str | None = None
    overseer_intervened: bool = False
    diff_at_review: str | None = None

    def to_json(self) -> dict:
        out: dict = {
            "cycle": self.cycle,
            "phase": self.phase,
            "runId": self.run_id,
            "status": self.status,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
        }
        if self.summary:
            out["summary"] = self.summary
        if self.trajectory:
            out["trajectory"] = [t.to_json() for t in self.trajectory]
        if self.spec_snapshot_sha:
            out["specSnapshotSha"] = self.spec_snapshot_sha
        if self.agents_snapshot_sha:
            out["agentsSnapshotSha"] = self.agents_snapshot_sha
        if self.overseer_intervened:
            out["overseerIntervened"] = True
        if self.diff_at_review:
            out["diffAtReview"] = self.diff_at_review
        return out

    @classmethod
    def from_json(cls, data: dict) -> CycleRecord:
        trajectory = [
            ToolCallTrace.from_json(t) for t in data.get("trajectory", [])
        ]
        return cls(
            cycle=data["cycle"],
            phase=data["phase"],
            run_id=data["runId"],
            status=data["status"],
            started_at=data["startedAt"],
            finished_at=data["finishedAt"],
            summary=data.get("summary"),
            trajectory=trajectory,
            spec_snapshot_sha=data.get("specSnapshotSha"),
            agents_snapshot_sha=data.get("agentsSnapshotSha"),
            overseer_intervened=bool(data.get("overseerIntervened")),
            diff_at_review=data.get("diffAtReview"),
        )


@dataclass
class CuriousState:
    version: int = STATE_VERSION
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
            "history": [r.to_json() for r in self.history],
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_json(cls, data: dict) -> CuriousState:
        version = data.get("version", 1)
        history = [CycleRecord.from_json(item) for item in data.get("history", [])]
        return cls(
            version=int(version),
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
