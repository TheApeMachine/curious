from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import VERIFIER_DEFAULT_MODEL, resolve_config
from curious.train.verifier_checkpoint import save_verifier_checkpoint
from curious.types import TrainConfig
from curious.verifier.architecture import build_verifier_model


def run_train_reviewer(
    config_path: str | None,
    *,
    base_model: str | None = None,
    dataset_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    """Train binary classifier: review PASS aligned with downstream task success."""
    try:
        import torch  # noqa: F401
        from torch.utils.data import Dataset  # noqa: F401
        from transformers import Trainer, TrainingArguments  # noqa: F401
    except ImportError as exc:
        raise ImportError("pip install 'curious-py[train]'") from exc

    import torch
    from torch.utils.data import Dataset
    from transformers import Trainer, TrainingArguments

    config = resolve_config(config_path=config_path, require_spec=False)
    train_cfg = config.train or TrainConfig()
    root = Path(config.project_root)

    data_file = (
        Path(dataset_path)
        if dataset_path
        else root / ".curious/harvest/reviewer.jsonl"
    )
    if not data_file.is_file():
        print(
            f"Missing {data_file} — run: curious-py harvest --format reviewer",
            file=sys.stderr,
        )
        sys.exit(1)

    model_id = base_model or (config.review_llm.model if config.review_llm else VERIFIER_DEFAULT_MODEL)
    if "/" not in model_id:
        model_id = VERIFIER_DEFAULT_MODEL

    out = Path(output_dir) if output_dir else root / ".curious/train/reviewer"
    out.mkdir(parents=True, exist_ok=True)

    rows = [
        json.loads(line)
        for line in data_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        sys.exit("No reviewer examples")

    model, tokenizer = build_verifier_model(model_id, num_labels=1)

    class ReviewerDataset(Dataset):
        def __len__(self) -> int:
            return len(rows)

        def __getitem__(self, i: int) -> dict:
            row = rows[i]
            text = (
                f"<|diff|>\n{row['diff_at_review'][:12000]}\n"
                f"<|verdict|>\n{json.dumps(row['review_verdict'])}\n"
            )
            enc = tokenizer(
                text,
                truncation=True,
                max_length=4096,
                padding="max_length",
                return_tensors="pt",
            )
            label = 1.0 if row["downstream_outcome"] == "clean" else 0.0
            if row["review_verdict"].get("overall") == "FAIL":
                label = 0.0
            return {
                "input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "labels": torch.tensor([label]),
            }

    args = TrainingArguments(
        output_dir=str(out),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_train_epochs=2,
        learning_rate=2e-5,
        logging_steps=10,
        bf16=True,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(model=model, args=args, train_dataset=ReviewerDataset())
    trainer.train()
    torch.save(model.state_dict(), out / "reviewer_head.pt")
    tokenizer.save_pretrained(out)
    save_verifier_checkpoint(
        out,
        base_model=model_id,
        state_dict_path="reviewer_head.pt",
    )
    (out / "curious_reviewer.json").write_text(
        json.dumps({"format": "curious-reviewer-v1", "base_model": model_id}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"[curious] train reviewer: saved to {out}")
