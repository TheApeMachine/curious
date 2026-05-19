from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from curious.harvest.dpo import DpoExample, harvest_dpo_pairs
from curious.state import load_state
from curious.types import ResolvedConfig

HarvestFormat = str


def _default_output_path(project_root: Path, fmt: str) -> Path:
    return project_root / ".curious" / "harvest" / f"{fmt}.jsonl"


def resolve_harvest_output(
    project_root: Path, fmt: str, configured: str | None, output_path: str | None
) -> Path:
    if output_path:
        resolved = Path(output_path)
        if not resolved.is_absolute():
            resolved = project_root / resolved
    elif configured:
        resolved = Path(configured)
        if not resolved.is_absolute():
            resolved = project_root / resolved
    else:
        return _default_output_path(project_root, fmt)

    if str(resolved).endswith(("/", "\\")):
        return resolved / f"{fmt}.jsonl"
    if resolved.suffix in ("", ".jsonl"):
        return resolved if resolved.suffix else resolved / f"{fmt}.jsonl"
    return resolved


def run_harvest(
    config: ResolvedConfig,
    *,
    fmt: str = "dpo",
    output_path: str | None = None,
    min_quality: float = 0.5,
    include_rejected: bool = False,
) -> tuple[Path, int, int]:
    if fmt != "dpo":
        raise ValueError(f"Unsupported harvest format: {fmt}")

    state = load_state(config.project_root)
    root = Path(config.project_root)
    out = resolve_harvest_output(
        root,
        fmt,
        config.harvest.output if config.harvest else None,
        output_path,
    )

    all_examples = harvest_dpo_pairs(
        state,
        project_root=config.project_root,
        cwd=config.cwd,
        spec_path=config.spec_path,
        min_quality=min_quality,
        include_rejected=include_rejected,
    )
    accepted = [e for e in all_examples if e.quality_score >= min_quality]
    skipped = len(all_examples) - len(accepted)

    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(e), ensure_ascii=False) for e in accepted]
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out, len(accepted), skipped
