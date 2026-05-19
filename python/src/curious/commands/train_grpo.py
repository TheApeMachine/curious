from __future__ import annotations

import json
import sys
from pathlib import Path

from curious.config import HF_DEFAULT_MODEL, resolve_config
from curious.spec_roadmap import analyze_roadmap
from curious.types import TrainConfig


def run_train_grpo(
    config_path: str | None,
    *,
    base_model: str | None = None,
    tasks_file: str | None = None,
    output_dir: str | None = None,
    n_rollouts_per_task: int = 4,
) -> None:
    try:
        import trl  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "GRPO requires: pip install 'curious-py[train]' with TRL >= 0.15"
        ) from exc

    config = resolve_config(config_path=config_path, require_spec=True)
    train_cfg = config.train or TrainConfig()
    root = Path(config.project_root)
    out = Path(output_dir) if output_dir else root / train_cfg.grpo_output_dir
    out.mkdir(parents=True, exist_ok=True)

    if tasks_file:
        tasks_path = Path(tasks_file)
    else:
        spec_body = Path(config.spec_path).read_text(encoding="utf-8")
        status = analyze_roadmap(spec_body)
        tasks = [
            {"task_id": tid, "prompt": f"Implement roadmap task {tid} per spec."}
            for tid in status.unchecked_task_ids
        ]
        tasks_path = out / "tasks.jsonl"
        tasks_path.write_text(
            "\n".join(json.dumps(t) for t in tasks) + ("\n" if tasks else ""),
            encoding="utf-8",
        )

    if not tasks_path.is_file():
        print(f"Tasks file not found: {tasks_path}", file=sys.stderr)
        sys.exit(1)

    model_id = base_model or config.llm.model
    if "/" not in model_id:
        model_id = HF_DEFAULT_MODEL

    print(
        f"[curious] train grpo: model={model_id} tasks={tasks_path} "
        f"rollouts={n_rollouts_per_task} → {out}"
    )
    print(
        "[curious] GRPO scaffold: wire TRL GRPOTrainer with verifier+scanner reward "
        "using harvested trajectories. Run develop cycles to populate state first."
    )

    readme = out / "README.txt"
    readme.write_text(
        "GRPO training entrypoint.\n"
        "1. curious-py harvest --format dpo\n"
        "2. curious-py train verifier\n"
        "3. Implement reward = verifier_score + scanner_penalty + reviewer_sample\n"
        "4. trl.GRPOTrainer on tasks.jsonl\n",
        encoding="utf-8",
    )
