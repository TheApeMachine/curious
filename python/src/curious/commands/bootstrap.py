from __future__ import annotations

import sys
from pathlib import Path

from curious.config import resolve_config
from curious.harness import run_harness
from curious.workspace import prepare_agent_workspace
from curious.project import DEFAULT_SPEC_REL
from curious.prompts_tasks import build_bootstrap_prompt


def run_bootstrap(config_path: str | None, verbose: bool) -> None:
    config = resolve_config(config_path=config_path, require_spec=False)
    prepare_agent_workspace(config)
    spec = Path(config.spec_path)

    if config.has_spec:
        print(f"[curious] {DEFAULT_SPEC_REL} exists — bootstrap will refine it")
    else:
        spec.parent.mkdir(parents=True, exist_ok=True)
        print(f"[curious] will create {DEFAULT_SPEC_REL}")

    prompt = build_bootstrap_prompt(config)
    result = run_harness(
        prompt,
        Path(config.cwd),
        config.llm,
        config.harness,
        verbose=verbose,
    )

    if result.status != "finished":
        print(f"[curious] bootstrap failed: {result.error}")
        sys.exit(1)

    print("\n[curious] Next steps:")
    print("  1. Review spec/SPEC.md")
    print("  2. curious-py roadmap")
    print("  3. curious-py run --cycle")
