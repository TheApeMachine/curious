from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import VERIFIER_DEFAULT_MODEL, resolve_config
from curious.types import CRITERION_KEYS, TrainConfig


def _require_train() -> None:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Verifier training requires: pip install 'curious-py[train]'"
        ) from exc


def run_train_verifier(
    config_path: str | None,
    *,
    base_model: str | None = None,
    dataset_path: str | None = None,
    output_dir: str | None = None,
) -> None:
    _require_train()

    import torch
    from torch import nn
    from torch.utils.data import Dataset
    from transformers import AutoModel, AutoTokenizer, Trainer, TrainingArguments

    config = resolve_config(config_path=config_path, require_spec=False)
    train_cfg = config.train or TrainConfig()
    root = Path(config.project_root)

    data_file = (
        Path(dataset_path)
        if dataset_path
        else root / ".curious/harvest/verifier.jsonl"
    )
    if not data_file.is_file():
        print(f"Missing {data_file} — run: curious-py harvest --format verifier", file=sys.stderr)
        sys.exit(1)

    model_id = base_model or config.verifier.base_model or VERIFIER_DEFAULT_MODEL
    out = Path(output_dir) if output_dir else root / train_cfg.verifier_output_dir
    out.mkdir(parents=True, exist_ok=True)

    rows = [
        json.loads(line)
        for line in data_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        print("No verifier examples", file=sys.stderr)
        sys.exit(1)

    print(f"[curious] train verifier: {len(rows)} examples, base={model_id}")

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    backbone = AutoModel.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    hidden = backbone.config.hidden_size
    num_labels = len(CRITERION_KEYS)

    class ModelWithHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.backbone = backbone
            self.classifier = nn.Linear(hidden, num_labels)

        def forward(self, input_ids, attention_mask=None, labels=None):
            out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
            last = out.last_hidden_state
            if attention_mask is not None:
                idx = attention_mask.sum(dim=1) - 1
                pooled = last[torch.arange(last.size(0)), idx]
            else:
                pooled = last[:, -1, :]
            logits = self.classifier(pooled)
            loss = None
            if labels is not None:
                loss = nn.functional.binary_cross_entropy_with_logits(
                    logits, labels.float()
                )
            return {"loss": loss, "logits": logits}

    model = ModelWithHead()

    class VerifierDataset(Dataset):
        def __len__(self) -> int:
            return len(rows)

        def __getitem__(self, i: int) -> dict:
            row = rows[i]
            text = (
                f"<|spec|>\n{row['spec_section']}\n"
                f"<|agents|>\n{row['agents_section']}\n"
                f"<|diff|>\n{row['diff']}\n"
            )
            enc = tokenizer(
                text,
                truncation=True,
                max_length=4096,
                padding="max_length",
                return_tensors="pt",
            )
            label_vec = [
                1.0 if row["labels"].get(k) else 0.0 for k in CRITERION_KEYS
            ]
            return {
                "input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "labels": torch.tensor(label_vec),
            }

    args = TrainingArguments(
        output_dir=str(out),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_train_epochs=2,
        learning_rate=2e-5,
        logging_steps=10,
        save_steps=100,
        bf16=True,
        report_to="none",
    )

    trainer = Trainer(model=model, args=args, train_dataset=VerifierDataset())
    trainer.train()
    torch.save(model.state_dict(), out / "verifier_head.pt")
    tokenizer.save_pretrained(out)
    print(f"[curious] train verifier: saved to {out}")
