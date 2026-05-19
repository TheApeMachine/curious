from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from curious.config import HF_DEFAULT_MODEL
from curious.llm_resolve import (
    hf_model_for_fallback,
    is_local_openai_compat_url,
    is_openai_compat_reachable,
    resolve_llm_for_harness,
    should_attempt_transformers_fallback,
)
from curious.types import LlmConfig


def test_is_local_url() -> None:
    assert is_local_openai_compat_url("http://127.0.0.1:11434/v1")
    assert not is_local_openai_compat_url("https://api.openai.com/v1")


def test_hf_model_mapping() -> None:
    llm = LlmConfig(provider="openai_compat", model="qwen3-coder:30b")
    assert hf_model_for_fallback(llm) == HF_DEFAULT_MODEL
    llm_hf = LlmConfig(provider="openai_compat", model="org/model")
    assert hf_model_for_fallback(llm_hf) == "org/model"
    llm_override = replace(llm, fallback_model="custom/model")
    assert hf_model_for_fallback(llm_override) == "custom/model"


def test_should_fallback_only_local_openai_compat() -> None:
    local = LlmConfig(provider="openai_compat", base_url="http://127.0.0.1:11434/v1")
    remote = LlmConfig(
        provider="openai_compat",
        base_url="https://example.com/v1",
    )
    transformers = LlmConfig(provider="transformers", model="Qwen/Qwen")
    assert should_attempt_transformers_fallback(local)
    assert not should_attempt_transformers_fallback(remote)
    assert not should_attempt_transformers_fallback(transformers)
    assert not should_attempt_transformers_fallback(
        replace(local, fallback_to_transformers=False)
    )


@patch("curious.llm_resolve.transformers_available", return_value=True)
@patch("curious.llm_resolve.is_openai_compat_reachable", return_value=False)
def test_resolve_switches_to_transformers(
    _reachable: object,
    _tf: object,
) -> None:
    llm = LlmConfig(
        provider="openai_compat",
        model="qwen3-coder:30b",
        base_url="http://127.0.0.1:11434/v1",
    )
    resolved = resolve_llm_for_harness(llm)
    assert resolved.provider == "transformers"
    assert resolved.model == HF_DEFAULT_MODEL
    assert resolved.device == "auto"


@patch("curious.llm_resolve.is_openai_compat_reachable", return_value=True)
def test_resolve_keeps_openai_compat_when_up(_reachable: object) -> None:
    llm = LlmConfig(
        provider="openai_compat",
        model="qwen3-coder:30b",
        base_url="http://127.0.0.1:11434/v1",
    )
    resolved = resolve_llm_for_harness(llm)
    assert resolved.provider == "openai_compat"
    assert resolved.model == "qwen3-coder:30b"


def test_unreachable_port() -> None:
    assert not is_openai_compat_reachable("http://127.0.0.1:1/v1", timeout_sec=0.2)
