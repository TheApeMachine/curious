from __future__ import annotations

import socket
from dataclasses import replace
from urllib.parse import urlparse

from curious.config import HF_DEFAULT_MODEL, VERIFIER_DEFAULT_MODEL
from curious.harness.providers.openai_compat import DEFAULT_LOCAL_BASE_URL
from curious.types import LlmConfig

# Ollama / local server tags → Hugging Face repo id when falling back to transformers.
_LOCAL_MODEL_TO_HF: dict[str, str] = {
    "qwen3-coder:30b": HF_DEFAULT_MODEL,
    "qwen3-coder": HF_DEFAULT_MODEL,
    "qwen3-coder-next": HF_DEFAULT_MODEL,
}

_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})


def is_local_openai_compat_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in _LOCAL_HOSTS


def is_openai_compat_reachable(
    base_url: str,
    *,
    timeout_sec: float = 2.0,
) -> bool:
    """Quick TCP probe — avoids waiting for a full chat request to time out."""
    parsed = urlparse(base_url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def transformers_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def hf_model_for_fallback(llm: LlmConfig) -> str:
    if llm.fallback_model:
        return llm.fallback_model
    if "/" in llm.model:
        return llm.model
    return _LOCAL_MODEL_TO_HF.get(llm.model, HF_DEFAULT_MODEL)


def should_attempt_transformers_fallback(llm: LlmConfig) -> bool:
    if not llm.fallback_to_transformers:
        return False
    if llm.provider != "openai_compat":
        return False
    base = (llm.base_url or DEFAULT_LOCAL_BASE_URL).rstrip("/")
    return is_local_openai_compat_url(base)


def resolve_llm_for_harness(llm: LlmConfig) -> LlmConfig:
    """
    Use configured provider when reachable. For local openai_compat (Ollama/vLLM),
    fall back to in-process transformers + Hugging Face weights when nothing is listening.
    """
    if not should_attempt_transformers_fallback(llm):
        return llm

    base = (llm.base_url or DEFAULT_LOCAL_BASE_URL).rstrip("/")
    if is_openai_compat_reachable(base):
        return llm

    hf_model = hf_model_for_fallback(llm)
    if not transformers_available():
        raise RuntimeError(
            f"Cannot reach LLM at {base} (connection refused) and transformers fallback "
            f"is not installed.\n"
            f"Either start Ollama/vLLM, or install local inference:\n"
            f"  pip install 'curious-py[transformers]'\n"
            f"Then re-run (will load {hf_model} from Hugging Face)."
        )

    print(
        f"[curious] LLM at {base} unreachable — loading {hf_model} via transformers "
        "(first run may download weights)"
    )
    device = llm.device if llm.device is not None else "auto"
    return replace(
        llm,
        provider="transformers",  # type: ignore[arg-type]
        model=hf_model,
        device=device,
    )
