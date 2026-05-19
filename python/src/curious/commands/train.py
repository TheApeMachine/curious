from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import HF_DEFAULT_MODEL, resolve_config
from curious.types import TrainConfig


def _require_train() -> None:
    try:
        import accelerate  # noqa: F401
        import datasets  # noqa: F401
        import peft  # noqa: F401
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import trl  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Training requires: pip install 'curious-py[train]' "
            "(transformers, trl, peft, datasets, accelerate)"
        ) from exc


def _load_dpo_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def run_train_dpo(
    config_path: str | None,
    *,
    dataset_path: str | None = None,
    model_id: str | None = None,
    output_dir: str | None = None,
    min_quality: float = 0.5,
) -> None:
    """DPO fine-tune with [TRL](https://huggingface.co/docs/trl/index) + [PEFT](https://huggingface.co/docs/peft/index)."""
    _require_train()

    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import DPOConfig, DPOTrainer

    config = resolve_config(config_path=config_path, require_spec=False)
    train_cfg = config.train or TrainConfig()
    project_root = Path(config.project_root)

    data_file = Path(dataset_path) if dataset_path else project_root / ".curious/harvest/dpo.jsonl"
    if not data_file.is_file():
        raise FileNotFoundError(
            f"DPO dataset not found: {data_file}\nRun: curious-py harvest --format dpo"
        )

    out_dir = Path(output_dir) if output_dir else project_root / train_cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base_model = model_id or config.llm.model
    if "/" not in base_model:
        base_model = HF_DEFAULT_MODEL

    raw = _load_dpo_jsonl(data_file)
    records = [
        {
            "prompt": row["prompt"],
            "chosen": row["chosen"],
            "rejected": row["rejected"],
        }
        for row in raw
        if float(row.get("quality_score", 0)) >= min_quality
    ]
    if not records:
        raise ValueError(f"No examples >= min_quality={min_quality} in {data_file}")

    print(f"[curious] train dpo: {len(records)} examples from {data_file}")
    print(f"[curious] train dpo: base model {base_model}")
    print(f"[curious] train dpo: output → {out_dir}")

    dataset = Dataset.from_list(records)
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
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

    dpo_args = DPOConfig(
        output_dir=str(out_dir),
        per_device_train_batch_size=train_cfg.per_device_train_batch_size,
        gradient_accumulation_steps=train_cfg.gradient_accumulation_steps,
        learning_rate=train_cfg.learning_rate,
        num_train_epochs=train_cfg.num_train_epochs,
        logging_steps=10,
        save_steps=100,
        bf16=True,
        max_length=train_cfg.max_length,
        max_prompt_length=train_cfg.max_prompt_length,
        report_to="none",
    )

    trainer = DPOTrainer(
        model=model,
        args=dpo_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    print(f"[curious] train dpo: saved adapter + tokenizer to {out_dir}")
    print(
        "[curious] next: serve merged weights (vLLM/Ollama) or set "
        'llm.provider=smolagents|transformers with the merged model path'
    )
