from __future__ import annotations

import uuid
from pathlib import Path

from curious.harness.native import run_native_harness
from curious.harness.result import HarnessResult
from curious.harness.smolagents_runner import run_smolagents_harness
from curious.llm_resolve import resolve_llm_for_harness
from curious.types import HarnessConfig, LlmConfig


def run_harness(
    prompt: str,
    workspace: Path,
    llm: LlmConfig,
    harness: HarnessConfig,
    *,
    verbose: bool = False,
) -> HarnessResult:
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    llm = resolve_llm_for_harness(llm)

    if llm.provider == "smolagents":
        return run_smolagents_harness(
            run_id,
            prompt,
            workspace,
            llm,
            harness,
            verbose=verbose,
        )

    return run_native_harness(
        run_id,
        prompt,
        workspace,
        llm,
        harness,
        verbose=verbose,
    )
