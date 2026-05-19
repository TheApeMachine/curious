from __future__ import annotations

import json
import os
from pathlib import Path

from curious.project import (
    CONFIG_FILENAME,
    DEFAULT_SPEC_REL,
    discover_project_in_parents,
    resolve_project_at_directory_sync,
    should_discover_parents,
)
from curious.types import (
    CuriousConfig,
    HarnessConfig,
    HarvestConfig,
    LlmConfig,
    LlmProvider,
    ResolvedConfig,
    TrainConfig,
)

HF_DEFAULT_MODEL = "Qwen/Qwen3-Coder-30B-A3B-Instruct"
from curious.harness.providers.openai_compat import (
    DEFAULT_LOCAL_API_KEY,
    DEFAULT_LOCAL_BASE_URL,
)
from curious.types import LlmProvider
from curious.workflow_policy import host_arch_label, is_arm64_host


def _default_provider() -> LlmProvider:
    raw = os.environ.get("CURIOUS_LLM_PROVIDER", "openai_compat")
    if raw in ("openai_compat", "litellm", "transformers", "smolagents"):
        return raw  # type: ignore[return-value]
    return "openai_compat"


def _default_model_for_provider(provider: LlmProvider) -> str:
    if provider in ("transformers", "smolagents"):
        return os.environ.get("LLM_MODEL", HF_DEFAULT_MODEL)
    if provider == "litellm":
        return os.environ.get("LLM_MODEL", "openai/gpt-5.5")
    return os.environ.get("LLM_MODEL", "qwen3-coder:30b")


def _default_config(project_root: Path, spec_path: Path) -> CuriousConfig:
    provider = _default_provider()
    return CuriousConfig(
        spec_path=str(spec_path),
        cwd=str(project_root),
        llm=LlmConfig(
            provider=provider,
            model=_default_model_for_provider(provider),
            api_key=os.environ.get("LLM_API_KEY")
            or (DEFAULT_LOCAL_API_KEY if provider == "openai_compat" else None),
            base_url=os.environ.get("LLM_BASE_URL")
            or (
                DEFAULT_LOCAL_BASE_URL if provider == "openai_compat" else None
            ),
        ),
        harness=HarnessConfig(),
        cycle_delay_ms=0,
        max_cycles=0,
        overseer_every_n_cycles=5,
        overseer_on_review_fail_streak=2,
    )


def _merge_dict(base: dict, override: dict) -> dict:
    out = {**base}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def _config_from_file_data(data: dict, resolve_relative_to: Path) -> dict:
    """Normalize JSON keys to snake_case-ish internal dict."""
    cwd = data.get("cwd", ".")
    cwd_path = Path(cwd) if Path(cwd).is_absolute() else resolve_relative_to / cwd

    spec = data.get("specPath", DEFAULT_SPEC_REL)
    spec_path = Path(spec) if Path(spec).is_absolute() else resolve_relative_to / spec

    llm_raw = data.get("llm", {})
    harness_raw = data.get("harness", {})
    harvest_raw = data.get("harvest")

    return {
        "spec_path": str(spec_path.resolve()),
        "cwd": str(cwd_path.resolve()),
        "llm": {
            "provider": llm_raw.get("provider")
            or os.environ.get("CURIOUS_LLM_PROVIDER", "openai_compat"),
            "model": llm_raw.get("model", os.environ.get("LLM_MODEL", "")),
            "api_key": llm_raw.get("apiKey") or llm_raw.get("api_key"),
            "base_url": llm_raw.get("baseUrl") or llm_raw.get("base_url"),
            "max_tokens": llm_raw.get("maxTokens", llm_raw.get("max_tokens", 16384)),
            "temperature": llm_raw.get("temperature", 0.2),
            "timeout_sec": llm_raw.get("timeoutSec", llm_raw.get("timeout_sec", 600)),
            "device": llm_raw.get("device"),
            "load_in_4bit": llm_raw.get("loadIn4bit", llm_raw.get("load_in_4bit", False)),
            "trust_remote_code": llm_raw.get(
                "trustRemoteCode", llm_raw.get("trust_remote_code", True)
            ),
            "smolagents_agent_type": llm_raw.get(
                "smolagentsAgentType",
                llm_raw.get("smolagents_agent_type", "tool-calling"),
            ),
        },
        "harness": {
            "max_turns": harness_raw.get("maxTurns", harness_raw.get("max_turns", 80)),
            "command_timeout_sec": harness_raw.get(
                "commandTimeoutSec",
                harness_raw.get("command_timeout_sec", 300),
            ),
        },
        "agent_branch": data.get("agentBranch", data.get("agent_branch", "curious")),
        "ensure_agent_branch": data.get(
            "ensureAgentBranch", data.get("ensure_agent_branch", True)
        ),
        "cycle_delay_ms": data.get("cycleDelayMs", data.get("cycle_delay_ms", 0)),
        "max_cycles": data.get("maxCycles", data.get("max_cycles", 0)),
        "overseer_every_n_cycles": data.get(
            "overseerEveryNCycles", data.get("overseer_every_n_cycles", 5)
        ),
        "overseer_on_review_fail_streak": data.get(
            "overseerOnReviewFailStreak",
            data.get("overseer_on_review_fail_streak", 2),
        ),
        "harvest": harvest_raw,
        "train": data.get("train"),
    }


def _dict_to_config(d: dict) -> CuriousConfig:
    llm_d = d["llm"]
    harness_d = d.get("harness", {})
    harvest_d = d.get("harvest")
    train_d = d.get("train")
    harvest = None
    if harvest_d:
        harvest = HarvestConfig(
            enabled=harvest_d.get("enabled", False),
            output=harvest_d.get("output", ".curious/harvest/"),
        )
    train = None
    if train_d:
        train = TrainConfig(
            output_dir=train_d.get("outputDir", train_d.get("output_dir", ".curious/train/dpo")),
            lora_r=int(train_d.get("loraR", train_d.get("lora_r", 16))),
            lora_alpha=int(train_d.get("loraAlpha", train_d.get("lora_alpha", 32))),
            learning_rate=float(
                train_d.get("learningRate", train_d.get("learning_rate", 5e-6))
            ),
            num_train_epochs=int(
                train_d.get("numTrainEpochs", train_d.get("num_train_epochs", 1))
            ),
            per_device_train_batch_size=int(
                train_d.get(
                    "perDeviceTrainBatchSize",
                    train_d.get("per_device_train_batch_size", 1),
                )
            ),
            gradient_accumulation_steps=int(
                train_d.get(
                    "gradientAccumulationSteps",
                    train_d.get("gradient_accumulation_steps", 4),
                )
            ),
            max_length=int(train_d.get("maxLength", train_d.get("max_length", 4096))),
            max_prompt_length=int(
                train_d.get("maxPromptLength", train_d.get("max_prompt_length", 2048))
            ),
        )
    provider = _normalize_provider(llm_d.get("provider"))
    return CuriousConfig(
        spec_path=d["spec_path"],
        cwd=d["cwd"],
        llm=LlmConfig(
            provider=provider,
            model=llm_d.get("model") or _default_model_for_provider(provider),
            api_key=llm_d.get("api_key") or os.environ.get("LLM_API_KEY"),
            base_url=llm_d.get("base_url") or os.environ.get("LLM_BASE_URL"),
            max_tokens=int(llm_d.get("max_tokens", 16384)),
            temperature=float(llm_d.get("temperature", 0.2)),
            timeout_sec=int(llm_d.get("timeout_sec", 600)),
            device=llm_d.get("device"),
            load_in_4bit=bool(llm_d.get("load_in_4bit", False)),
            trust_remote_code=bool(llm_d.get("trust_remote_code", True)),
            smolagents_agent_type=llm_d.get("smolagents_agent_type", "tool-calling"),  # type: ignore[arg-type]
        ),
        harness=HarnessConfig(
            max_turns=int(harness_d.get("max_turns", 80)),
            command_timeout_sec=int(harness_d.get("command_timeout_sec", 300)),
        ),
        agent_branch=str(d.get("agent_branch", "curious")),
        ensure_agent_branch=bool(d.get("ensure_agent_branch", True)),
        cycle_delay_ms=int(d.get("cycle_delay_ms", 0)),
        max_cycles=int(d.get("max_cycles", 0)),
        overseer_every_n_cycles=int(d.get("overseer_every_n_cycles", 5)),
        overseer_on_review_fail_streak=int(d.get("overseer_on_review_fail_streak", 2)),
        harvest=harvest,
        train=train,
    )


def _normalize_provider(raw: str | None) -> LlmProvider:
    if raw in ("openai_compat", "litellm", "transformers", "smolagents"):
        return raw  # type: ignore[return-value]
    return "openai_compat"


def _validate_llm(config: CuriousConfig) -> None:
    if config.llm.provider == "litellm" and not config.llm.api_key:
        raise ValueError(
            "llm.provider=litellm requires LLM_API_KEY (or curious.config.json llm.apiKey). "
            "For local Ollama/vLLM use llm.provider=openai_compat (default)."
        )
    if config.llm.provider == "openai_compat":
        if not config.llm.base_url:
            config.llm.base_url = DEFAULT_LOCAL_BASE_URL
        if not config.llm.api_key:
            config.llm.api_key = DEFAULT_LOCAL_API_KEY
    if config.llm.provider in ("transformers", "smolagents"):
        if "/" not in config.llm.model:
            raise ValueError(
                f"llm.provider={config.llm.provider} expects a Hugging Face repo id "
                f"(e.g. {HF_DEFAULT_MODEL}), got {config.llm.model!r}"
            )
        if config.llm.device is None:
            config.llm.device = "auto"


def config_from_env() -> dict:
    partial: dict = {}
    if os.environ.get("CURIOUS_LLM_PROVIDER"):
        partial.setdefault("llm", {})["provider"] = os.environ["CURIOUS_LLM_PROVIDER"]
    if os.environ.get("CURIOUS_SPEC_PATH"):
        partial["specPath"] = os.environ["CURIOUS_SPEC_PATH"]
    if os.environ.get("CURIOUS_CWD"):
        partial["cwd"] = os.environ["CURIOUS_CWD"]
    if os.environ.get("LLM_MODEL"):
        partial.setdefault("llm", {})["model"] = os.environ["LLM_MODEL"]
    if os.environ.get("LLM_API_KEY"):
        partial.setdefault("llm", {})["apiKey"] = os.environ["LLM_API_KEY"]
    if os.environ.get("LLM_BASE_URL"):
        partial.setdefault("llm", {})["baseUrl"] = os.environ["LLM_BASE_URL"]
    if os.environ.get("CURIOUS_CYCLE_DELAY_MS"):
        partial["cycleDelayMs"] = int(os.environ["CURIOUS_CYCLE_DELAY_MS"])
    if os.environ.get("CURIOUS_MAX_CYCLES"):
        partial["maxCycles"] = int(os.environ["CURIOUS_MAX_CYCLES"])
    if os.environ.get("CURIOUS_OVERSEER_EVERY_N_CYCLES"):
        partial["overseerEveryNCycles"] = int(os.environ["CURIOUS_OVERSEER_EVERY_N_CYCLES"])
    if os.environ.get("CURIOUS_OVERSEER_FAIL_STREAK"):
        partial["overseerOnReviewFailStreak"] = int(os.environ["CURIOUS_OVERSEER_FAIL_STREAK"])
    if os.environ.get("CURIOUS_AGENT_BRANCH"):
        partial["agentBranch"] = os.environ["CURIOUS_AGENT_BRANCH"]
    if os.environ.get("CURIOUS_ENSURE_AGENT_BRANCH") is not None:
        partial["ensureAgentBranch"] = os.environ["CURIOUS_ENSURE_AGENT_BRANCH"].lower() in (
            "1",
            "true",
            "yes",
        )
    return partial


def resolve_config(
    config_path: str | None = None,
    require_spec: bool = True,
) -> ResolvedConfig:
    if config_path:
        cfg_file = Path(config_path).resolve()
        located = resolve_project_at_directory_sync(cfg_file.parent)
        located.config_path = cfg_file
    else:
        start = Path(os.environ.get("CURIOUS_CWD", Path.cwd()))
        if should_discover_parents():
            located = discover_project_in_parents(start)
            if located is None:
                located = resolve_project_at_directory_sync(start)
        else:
            located = resolve_project_at_directory_sync(start)

    if require_spec and not located.has_spec:
        raise FileNotFoundError(
            f"No {DEFAULT_SPEC_REL} in {located.project_root}.\n"
            "Run from project root or: curious-py bootstrap"
        )

    base = _default_config(located.project_root, located.spec_path)
    merged = _config_from_file_data(
        {
            "specPath": base.spec_path,
            "cwd": base.cwd,
            "llm": {
                "provider": base.llm.provider,
                "model": base.llm.model,
                "apiKey": base.llm.api_key,
                "baseUrl": base.llm.base_url,
                "maxTokens": base.llm.max_tokens,
                "temperature": base.llm.temperature,
                "timeoutSec": base.llm.timeout_sec,
            },
            "harness": {
                "maxTurns": base.harness.max_turns,
                "commandTimeoutSec": base.harness.command_timeout_sec,
            },
            "cycleDelayMs": base.cycle_delay_ms,
            "maxCycles": base.max_cycles,
            "overseerEveryNCycles": base.overseer_every_n_cycles,
            "overseerOnReviewFailStreak": base.overseer_on_review_fail_streak,
        },
        located.project_root,
    )

    if located.config_path and located.config_path.is_file():
        file_data = json.loads(located.config_path.read_text(encoding="utf-8"))
        file_norm = _config_from_file_data(file_data, located.project_root)
        merged = _merge_dict(merged, file_norm)

    env_data = config_from_env()
    if env_data:
        env_norm = _config_from_file_data(
            {**merged, **env_data},
            located.project_root,
        )
        merged = _merge_dict(merged, env_norm)

    config = _dict_to_config(merged)
    _validate_llm(config)

    return ResolvedConfig(
        spec_path=config.spec_path,
        cwd=config.cwd,
        llm=config.llm,
        harness=config.harness,
        agent_branch=config.agent_branch,
        ensure_agent_branch=config.ensure_agent_branch,
        cycle_delay_ms=config.cycle_delay_ms,
        max_cycles=config.max_cycles,
        overseer_every_n_cycles=config.overseer_every_n_cycles,
        overseer_on_review_fail_streak=config.overseer_on_review_fail_streak,
        harvest=config.harvest,
        train=config.train,
        project_root=str(located.project_root),
        has_spec=located.has_spec,
    )


def print_config_summary(config: ResolvedConfig) -> None:
    print(f"[curious] project root: {config.project_root}")
    spec_note = "" if config.has_spec else " (will be created)"
    print(f"[curious] spec: {config.spec_path}{spec_note}")
    print(f"[curious] agent cwd: {config.cwd}")
    print(f"[curious] llm: {config.llm.provider} · {config.llm.model}")
    if config.llm.provider == "openai_compat":
        print(f"[curious] llm endpoint: {config.llm.base_url}")
    if config.llm.provider in ("transformers", "smolagents"):
        print(f"[curious] llm device: {config.llm.device}")
        if config.llm.provider == "smolagents":
            print(f"[curious] smolagents agent: {config.llm.smolagents_agent_type}")
    arch = host_arch_label()
    amd64_note = "; amd64-tagged tests N/A" if is_arm64_host() else ""
    print(f"[curious] host: {arch} (verify on this arch only{amd64_note})")
    print("[curious] commits: human only (agents must not git commit)")
    if config.ensure_agent_branch:
        from curious.git_branch import current_branch, git_toplevel

        root = git_toplevel(Path(config.project_root))
        branch = current_branch(root) if root else None
        print(
            f"[curious] git branch: {branch or config.agent_branch}"
            + (" (will switch before agent runs)" if root and branch != config.agent_branch else "")
        )
    if config.overseer_every_n_cycles > 0 or config.overseer_on_review_fail_streak > 0:
        parts = []
        if config.overseer_every_n_cycles > 0:
            parts.append(f"every {config.overseer_every_n_cycles} task cycle(s)")
        if config.overseer_on_review_fail_streak > 0:
            parts.append(f"after {config.overseer_on_review_fail_streak} review FAIL(s)")
        print(f"[curious] overseer: {'; '.join(parts)}")
    else:
        print("[curious] overseer: disabled")
