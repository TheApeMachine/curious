from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import HF_DEFAULT_MODEL, VERIFIER_DEFAULT_MODEL, resolve_config
from curious.harvest.grpo import harvest_grpo_tasks
from curious.project import AGENTS_FILENAME
from curious.state import load_state
from curious.train.grpo_reward import make_grpo_reward_fn
from curious.types import ResolvedConfig, TrainConfig
from curious.vast.dispatch import dispatch_training


def _require_train() -> None:
    try:
        import trl  # noqa: F401
        from peft import LoraConfig  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "GRPO requires: pip install 'curious-py[train]'"
        ) from exc


def _load_tasks_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _ensure_tasks_file(config, root: Path, out: Path, tasks_file: str | None) -> Path:
    if tasks_file:
        return Path(tasks_file)

    harvest_path = root / ".curious/harvest/grpo.jsonl"
    if harvest_path.is_file():
        return harvest_path

    state = load_state(config.project_root)
    examples = harvest_grpo_tasks(
        state,
        project_root=config.project_root,
        spec_path=config.spec_path,
    )
    if not examples:
        raise ValueError(
            "No GRPO tasks — add Roadmap T* tasks to spec or run develop cycles first"
        )

    harvest_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(ex.to_json(), ensure_ascii=False) for ex in examples]
    harvest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[curious] wrote {len(examples)} GRPO prompts → {harvest_path}")
    return harvest_path


def run_train_grpo(
    config_path: str | None,
    *,
    base_model: str | None = None,
    tasks_file: str | None = None,
    output_dir: str | None = None,
    n_rollouts_per_task: int = 4,
    max_completion_length: int = 2048,
    num_epochs: int = 1,
    force_local: bool = False,
    force_vast: bool | None = None,
) -> None:
    """GRPO fine-tune with TRL — composite verifier + heuristic reward."""
    config = resolve_config(config_path=config_path, require_spec=True)

    def local() -> None:
        _run_train_grpo_local(
            config,
            base_model=base_model,
            tasks_file=tasks_file,
            output_dir=output_dir,
            n_rollouts_per_task=n_rollouts_per_task,
            max_completion_length=max_completion_length,
            num_epochs=num_epochs,
        )

    flags: dict = {"rollouts": n_rollouts_per_task, "epochs": num_epochs}
    if tasks_file:
        flags["tasks_file"] = tasks_file
    if base_model:
        flags["model"] = base_model
    if output_dir:
        flags["output"] = output_dir
    flags["max_completion_length"] = max_completion_length

    dispatch_training(
        config,
        kind="grpo",
        label="grpo",
        local_runner=local,
        config_path=config_path,
        force_local=force_local,
        force_vast=force_vast,
        train_flags=flags,
    )


def _run_train_grpo_local(
    config: ResolvedConfig,
    *,
    base_model: str | None,
    tasks_file: str | None,
    output_dir: str | None,
    n_rollouts_per_task: int,
    max_completion_length: int,
    num_epochs: int,
) -> None:
    _require_train()

    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    train_cfg = config.train or TrainConfig()
    root = Path(config.project_root)
    out = Path(output_dir) if output_dir else root / train_cfg.grpo_output_dir
    out.mkdir(parents=True, exist_ok=True)

    tasks_path = _ensure_tasks_file(config, root, out, tasks_file)
    raw_tasks = _load_tasks_jsonl(tasks_path)
    if not raw_tasks:
        print(f"No tasks in {tasks_path}", file=sys.stderr)
        sys.exit(1)

    records = [
        {
            "prompt": row["prompt"],
            "spec_section": row.get("spec_section", ""),
            "agents_section": row.get("agents_section", ""),
            "task_id": row.get("task_id", ""),
        }
        for row in raw_tasks
    ]

    model_id = base_model or config.llm.model
    if "/" not in model_id:
        model_id = HF_DEFAULT_MODEL

    verifier_ckpt = config.verifier.model_path
    if verifier_ckpt and not Path(verifier_ckpt).is_absolute():
        verifier_ckpt = str(root / verifier_ckpt)

    reward_fn = make_grpo_reward_fn(
        root,
        verifier_checkpoint=verifier_ckpt,
        verifier_base_model=config.verifier.base_model or VERIFIER_DEFAULT_MODEL,
        spec_path=config.spec_path,
        agents_path=str(root / AGENTS_FILENAME),
    )

    print(f"[curious] train grpo: {len(records)} prompts from {tasks_path}")
    print(f"[curious] train grpo: policy model {model_id}")
    print(f"[curious] train grpo: num_generations={n_rollouts_per_task}")
    print(f"[curious] train grpo: output → {out}")

    dataset = Dataset.from_list(records)
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )

    peft_config = LoraConfig(
        r=train_cfg.lora_r,
        lora_alpha=train_cfg.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    grpo_args = GRPOConfig(
        output_dir=str(out),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=train_cfg.gradient_accumulation_steps,
        num_train_epochs=num_epochs,
        learning_rate=train_cfg.learning_rate,
        logging_steps=10,
        save_steps=100,
        bf16=True,
        report_to="none",
        remove_unused_columns=False,
        num_generations=n_rollouts_per_task,
        max_completion_length=max_completion_length,
        temperature=0.8,
    )

    trainer = GRPOTrainer(
        model=model,
        reward_funcs=reward_fn,
        args=grpo_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(str(out))
    tokenizer.save_pretrained(out)

    adapter_meta = {
        "format": "curious-grpo-lora-v1",
        "base_model": model_id,
        "adapter_dir": str(out),
    }
    (out / "curious_grpo.json").write_text(
        json.dumps(adapter_meta, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[curious] train grpo: saved LoRA adapter to {out}")
    print(f"[curious] set llm.adapterPath to {out} and llm.provider to transformers|smolagents")
