from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from curious.types import CRITERION_KEYS

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
        import torch

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
            outputs = self.model(**inputs)
            if hasattr(outputs, "logits"):
                logits = outputs.logits
            else:
                logits = outputs[0]
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
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    path = model_path or base_model
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    try:
        model = AutoModelForSequenceClassification.from_pretrained(
            path,
            num_labels=num_labels,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
    except Exception:
        from transformers import AutoModel
        import torch.nn as nn

        backbone = AutoModel.from_pretrained(
            base_model,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
        hidden = backbone.config.hidden_size

        class ClassifierHead(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.head = nn.Linear(hidden, num_labels)

            def forward(self, **kwargs):
                out = backbone(**kwargs)
                last = out.last_hidden_state
                mask = kwargs.get("attention_mask")
                if mask is not None:
                    idx = mask.sum(dim=1) - 1
                    pooled = last[torch.arange(last.size(0)), idx]
                else:
                    pooled = last[:, -1, :]
                return type("Out", (), {"logits": self.head(pooled)})()

        model = ClassifierHead()
        tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)

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
