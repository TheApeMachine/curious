from __future__ import annotations

"""Map curious `llm.device` to Hugging Face load kwargs.

`device_map` for `from_pretrained` accepts `auto`, `cpu`, `cuda`, `balanced`, or a
per-layer dict — **not** `mps`. On Apple Silicon, `device_map="auto"` lets
Transformers/accelerate place weights on MPS when supported.
"""

from curious.types import LlmConfig


def resolve_device_map(llm: LlmConfig) -> str:
    """Return a valid `device_map` argument for `AutoModelForCausalLM.from_pretrained`."""
    if llm.device:
        normalized = llm.device.strip().lower()
        if normalized == "mps":
            # User means Apple GPU; HF route is auto (not the string "mps").
            return "auto"
        if normalized in ("auto", "cpu", "cuda", "balanced"):
            return normalized
        # cuda:0, etc. — let accelerate interpret via auto
        return "auto"

    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available() or torch.backends.mps.is_available():
        return "auto"
    return "cpu"
