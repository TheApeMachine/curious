from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import torch

from curious.train.verifier_checkpoint import CHECKPOINT_META, load_verifier_meta
from curious.types import CRITERION_KEYS
from curious.verifier.architecture import build_verifier_model

VERIFIER_INPUT_TEMPLATE = (
    "<|spec|>\n{spec_section}\n<|agents|>\n{agents_section}\n<|diff|>\n{diff}\n"
)


@dataclass
class VerifierScores:
    labels: dict[str, float]
    overall: float

    def predicted_pass(self, threshold: float = 0.5) -> bool:
        return self.overall >= threshold


class VerifierModel:
    """Multi-label classifier over (spec + agents + diff) → six criteria."""

    def __init__(self, model, tokenizer, device) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.device = device

    def score(
        self,
        *,
        diff: str,
        spec_section: str,
        agents_section: str,
        max_length: int = 4096,
    ) -> VerifierScores:
        text = VERIFIER_INPUT_TEMPLATE.format(
            spec_section=spec_section[:8000],
            agents_section=agents_section[:4000],
            diff=_truncate_diff_middle(diff, max_length // 2),
        )
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            self.model.eval()
            outputs = self.model(**inputs)
            logits = outputs["logits"] if isinstance(outputs, dict) else outputs.logits
            if logits.dim() > 1:
                logits = logits[0]
            probs = torch.sigmoid(logits).cpu().tolist()

        labels = {
            key: float(probs[i]) if i < len(probs) else 0.0
            for i, key in enumerate(CRITERION_KEYS)
        }
        overall = sum(labels.values()) / len(labels) if labels else 0.0
        return VerifierScores(labels=labels, overall=overall)


def _truncate_diff_middle(diff: str, max_chars: int) -> str:
    if len(diff) <= max_chars:
        return diff
    head = max_chars // 2
    tail = max_chars - head - 40
    return diff[:head] + "\n… [diff truncated] …\n" + diff[-tail:]


def load_verifier(
    model_path: str | None,
    base_model: str,
    *,
    num_labels: int = len(CRITERION_KEYS),
) -> VerifierModel:
    checkpoint_dir = Path(model_path) if model_path else None
    meta = (
        load_verifier_meta(checkpoint_dir)
        if checkpoint_dir and checkpoint_dir.is_dir()
        else None
    )

    if meta and meta.get("format") == "curious-verifier-v1":
        base_model = meta.get("base_model", base_model)
        model, tokenizer = build_verifier_model(base_model, num_labels=num_labels)
        state_file = checkpoint_dir / meta.get("state_dict", "verifier_head.pt")
        if state_file.is_file():
            state = torch.load(state_file, map_location="cpu", weights_only=True)
            model.load_state_dict(state, strict=True)
        tok_dir = checkpoint_dir
        if (tok_dir / "tokenizer_config.json").is_file():
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(str(tok_dir), trust_remote_code=True)
        device = next(model.parameters()).device
        model.eval()
        return VerifierModel(model, tokenizer, device)

    model, tokenizer = build_verifier_model(base_model, num_labels=num_labels)
    device = next(model.parameters()).device
    model.eval()
    return VerifierModel(model, tokenizer, device)


def log_disagreement(
    project_root: Path,
    log_path: str,
    *,
    cycle: int,
    verifier_scores: VerifierScores,
    reviewer_pass: bool,
    diff_excerpt: str,
) -> None:
    predicted_pass = verifier_scores.predicted_pass(0.7)
    if predicted_pass == reviewer_pass:
        return
    path = project_root / log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "cycle": cycle,
        "verifierOverall": verifier_scores.overall,
        "verifierLabels": verifier_scores.labels,
        "reviewerPass": reviewer_pass,
        "diffExcerpt": diff_excerpt[:2000],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
