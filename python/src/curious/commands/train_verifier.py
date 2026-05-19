from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import VERIFIER_DEFAULT_MODEL, resolve_config
from curious.train.verifier_checkpoint import save_verifier_checkpoint
from curious.types import CRITERION_KEYS, ResolvedConfig, TrainConfig
from curious.vast.dispatch import dispatch_training
from curious.verifier.architecture import build_verifier_model


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
    force_local: bool = False,
    force_vast: bool | None = None,
) -> None:
    config = resolve_config(config_path=config_path, require_spec=False)

    def local() -> None:
        _run_train_verifier_local(
            config,
            base_model=base_model,
            dataset_path=dataset_path,
            output_dir=output_dir,
        )

    flags: dict = {}
    if dataset_path:
        flags["dataset"] = dataset_path
    if base_model:
        flags["model"] = base_model
    if output_dir:
        flags["output"] = output_dir

    dispatch_training(
        config,
        kind="verifier",
        label="verifier",
        local_runner=local,
        config_path=config_path,
        force_local=force_local,
        force_vast=force_vast,
        train_flags=flags,
    )


def _run_train_verifier_local(
    config: ResolvedConfig,
    *,
    base_model: str | None,
    dataset_path: str | None,
    output_dir: str | None,
) -> None:
    _require_train()

    import torch
    from torch.utils.data import Dataset
    from transformers import Trainer, TrainingArguments

    train_cfg = config.train or TrainConfig()
    root = Path(config.project_root)

    data_file = (
        Path(dataset_path)
        if dataset_path
        else root / ".curious/harvest/verifier.jsonl"
    )
    if not data_file.is_file():
        print(
            f"Missing {data_file} — run: curious-py harvest --format verifier",
            file=sys.stderr,
        )
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

    model, tokenizer = build_verifier_model(model_id)

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
        save_steps=500,
        bf16=True,
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(model=model, args=args, train_dataset=VerifierDataset())
    trainer.train()

    state_path = out / "verifier_head.pt"
    torch.save(model.state_dict(), state_path)
    tokenizer.save_pretrained(out)
    save_verifier_checkpoint(out, base_model=model_id, state_dict_path=state_path.name)

    print(f"[curious] train verifier: saved checkpoint to {out}")
    print(f"[curious] set verifier.modelPath to {out} in curious.config.json")
