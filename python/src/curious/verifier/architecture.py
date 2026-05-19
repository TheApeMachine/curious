from __future__ import annotations

from typing import Any

from curious.types import CRITERION_KEYS


def build_verifier_model(base_model_id: str, num_labels: int | None = None) -> tuple[Any, Any]:
    """Backbone + linear multi-label head (pool last token)."""
    import torch
    import torch.nn.functional as F
    from torch import nn
    from transformers import AutoModel, AutoTokenizer

    n = num_labels or len(CRITERION_KEYS)
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    backbone = AutoModel.from_pretrained(
        base_model_id,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    hidden = backbone.config.hidden_size

    class ModelWithHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.backbone = backbone
            self.classifier = nn.Linear(hidden, n)

        def forward(self, input_ids=None, attention_mask=None, labels=None, **kwargs):
            out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
            last = out.last_hidden_state
            if attention_mask is not None:
                idx = attention_mask.sum(dim=1) - 1
                pooled = last[torch.arange(last.size(0), device=last.device), idx]
            else:
                pooled = last[:, -1, :]
            logits = self.classifier(pooled)
            loss = None
            if labels is not None:
                loss = F.binary_cross_entropy_with_logits(
                    logits.float(), labels.float()
                )
            return {"loss": loss, "logits": logits}

    return ModelWithHead(), tokenizer
