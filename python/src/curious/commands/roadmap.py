from __future__ import annotations

import sys
from pathlib import Path

from curious.config import resolve_config
from curious.harness import run_harness
from curious.prompts_tasks import build_roadmap_prompt


def run_roadmap(config_path: str | None, verbose: bool) -> None:
    config = resolve_config(config_path=config_path, require_spec=True)
    spec_body = Path(config.spec_path).read_text(encoding="utf-8")
    prompt = build_roadmap_prompt(config, spec_body)
    result = run_harness(
        prompt,
        Path(config.cwd),
        config.llm,
        config.harness,
        verbose=verbose,
    )

    if result.status != "finished":
        print(f"[curious] roadmap failed: {result.error}")
        sys.exit(1)

    print("\n[curious] Next: curious-py run --cycle")
