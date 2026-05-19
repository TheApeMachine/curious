from __future__ import annotations

from pathlib import Path

from curious.harness.result import HarnessResult, SYSTEM_PROMPT
from curious.harness.smolagents_tools import build_smolagents_tools
from curious.types import HarnessConfig, LlmConfig


def run_smolagents_harness(
    run_id: str,
    prompt: str,
    workspace: Path,
    llm: LlmConfig,
    harness: HarnessConfig,
    *,
    verbose: bool = False,
) -> HarnessResult:
    """Agent loop via [smolagents](https://huggingface.co/docs/smolagents/index) + TransformersModel."""
    try:
        from smolagents import CodeAgent, ToolCallingAgent, TransformersModel
    except ImportError as exc:
        return HarnessResult(
            run_id=run_id,
            status="error",
            summary=None,
            error=(
                "llm.provider=smolagents requires: pip install 'curious-py[smolagents]' "
                f"({exc})"
            ),
        )

    device_map = llm.device or "auto"
    model = TransformersModel(
        model_id=llm.model,
        device_map=device_map,
        torch_dtype="auto",
        max_new_tokens=min(llm.max_tokens, 8192),
        trust_remote_code=llm.trust_remote_code,
    )

    tools = build_smolagents_tools(workspace, harness.command_timeout_sec)
    max_steps = harness.max_turns

    if llm.smolagents_agent_type == "code":
        agent = CodeAgent(
            tools=tools,
            model=model,
            max_steps=max_steps,
            verbosity_level=2 if verbose else 1,
        )
    else:
        agent = ToolCallingAgent(
            tools=tools,
            model=model,
            max_steps=max_steps,
            verbosity_level=2 if verbose else 1,
        )

    full_prompt = f"{SYSTEM_PROMPT}\n\n---\n\n{prompt}"

    try:
        result = agent.run(full_prompt)
        summary = str(result).strip()
        return HarnessResult(
            run_id=run_id,
            status="finished",
            summary=summary,
            turns=max_steps,
        )
    except Exception as exc:
        return HarnessResult(
            run_id=run_id,
            status="error",
            summary=None,
            error=str(exc),
        )
