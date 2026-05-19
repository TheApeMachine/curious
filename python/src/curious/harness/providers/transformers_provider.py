from __future__ import annotations

from typing import Any

from curious.harness.providers.device_load import resolve_device_map
from curious.harness.providers.tool_call_parsers import (
    parse_tool_calls_from_text,
    strip_tool_call_markup,
)
from curious.harness.providers.types import ChatCompletion, ToolCall
from curious.types import LlmConfig

_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}


def _require_transformers() -> None:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "llm.provider=transformers requires: pip install 'curious-py[transformers]'"
        ) from exc


def _load_model(llm: LlmConfig) -> tuple[Any, Any]:
    cache_key = f"{llm.model}::{llm.adapter_path or ''}"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    _require_transformers()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        llm.model,
        trust_remote_code=llm.trust_remote_code,
    )
    load_kwargs: dict[str, Any] = {
        "trust_remote_code": llm.trust_remote_code,
        "torch_dtype": "auto",
        "device_map": resolve_device_map(llm),
    }
    if llm.load_in_4bit:
        from transformers import BitsAndBytesConfig

        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)

    model = AutoModelForCausalLM.from_pretrained(llm.model, **load_kwargs)

    if llm.adapter_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, llm.adapter_path)

    cache_key = f"{llm.model}::{llm.adapter_path or ''}"
    _MODEL_CACHE[cache_key] = (tokenizer, model)
    return tokenizer, model


def _model_device(model: Any) -> Any:
    if hasattr(model, "device"):
        return model.device
    return next(model.parameters()).device


class TransformersProvider:
    """Local inference via [Transformers](https://huggingface.co/docs/transformers/index)."""

    def __init__(self, llm: LlmConfig) -> None:
        self.llm = llm
        self.tokenizer, self.model = _load_model(llm)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatCompletion:
        import torch

        template_kwargs: dict[str, Any] = {
            "tokenize": False,
            "add_generation_prompt": True,
        }
        try:
            text = self.tokenizer.apply_chat_template(
                messages,
                tools=tools,
                **template_kwargs,
            )
        except TypeError:
            text = self.tokenizer.apply_chat_template(messages, **template_kwargs)

        inputs = self.tokenizer(text, return_tensors="pt")
        device = _model_device(self.model)
        inputs = {key: value.to(device) for key, value in inputs.items()}

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": min(self.llm.max_tokens, 8192),
            "do_sample": self.llm.temperature > 0,
        }
        if self.llm.temperature > 0:
            gen_kwargs["temperature"] = self.llm.temperature

        with torch.no_grad():
            output = self.model.generate(**inputs, **gen_kwargs)

        new_tokens = output[0, inputs["input_ids"].shape[1] :]
        decoded = self.tokenizer.decode(new_tokens, skip_special_tokens=False)
        stripped = decoded.strip()

        tool_calls = parse_tool_calls_from_text(stripped, self.llm.model)
        content = strip_tool_call_markup(stripped, self.llm.model)

        return ChatCompletion(content=content, tool_calls=tool_calls)
