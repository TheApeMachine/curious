from curious.harness.providers.device_load import resolve_device_map
from curious.types import LlmConfig


def test_mps_maps_to_auto_not_invalid_device_map():
    llm = LlmConfig(provider="transformers", model="Qwen/Qwen3-Coder-30B-A3B-Instruct", device="mps")
    assert resolve_device_map(llm) == "auto"
    assert resolve_device_map(llm) != "mps"


def test_explicit_auto_unchanged():
    llm = LlmConfig(provider="transformers", model="Qwen/Qwen3-Coder-30B-A3B-Instruct", device="auto")
    assert resolve_device_map(llm) == "auto"
