from __future__ import annotations

import json
import re
from typing import Any

from curious.harness.providers.types import ChatCompletion, ToolCall
from curious.types import LlmConfig

_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}

# Qwen-style tool blocks in generated text
_TOOL_CALL_BLOCK = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


def _require_transformers() -> None:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "llm.provider=transformers requires: pip install 'curious-py[transformers]'"
        ) from exc


def _resolve_device_map(llm: LlmConfig) -> str:
    if llm.device:
        return llm.device
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "auto"
    return "cpu"


def _load_model(llm: LlmConfig) -> tuple[Any, Any]:
    if llm.model in _MODEL_CACHE:
        return _MODEL_CACHE[llm.model]

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
        "device_map": _resolve_device_map(llm),
    }
    if llm.load_in_4bit:
        from transformers import BitsAndBytesConfig

        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)

    model = AutoModelForCausalLM.from_pretrained(llm.model, **load_kwargs)
    _MODEL_CACHE[llm.model] = (tokenizer, model)
    return tokenizer, model


def _parse_tool_calls_from_text(text: str) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, match in enumerate(_TOOL_CALL_BLOCK.finditer(text)):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = payload.get("name") or payload.get("function", "")
        args = payload.get("arguments", {})
        if isinstance(args, dict):
            args_str = json.dumps(args)
        else:
            args_str = str(args)
        calls.append(
            ToolCall(
                id=f"call_{index}",
                name=name,
                arguments=args_str,
            )
        )
    return calls


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

        tool_calls = _parse_tool_calls_from_text(stripped)
        content = _TOOL_CALL_BLOCK.sub("", stripped).strip()

        return ChatCompletion(content=content, tool_calls=tool_calls)
