from __future__ import annotations

import json
from pathlib import Path

from curious.types import CRITERION_KEYS

CHECKPOINT_META = "curious_verifier.json"


def save_verifier_checkpoint(
    out_dir: Path,
    *,
    base_model: str,
    state_dict_path: str = "verifier_head.pt",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "format": "curious-verifier-v1",
        "base_model": base_model,
        "num_labels": len(CRITERION_KEYS),
        "criterion_keys": list(CRITERION_KEYS),
        "state_dict": state_dict_path,
    }
    (out_dir / CHECKPOINT_META).write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )


def load_verifier_meta(checkpoint_dir: Path) -> dict | None:
    path = checkpoint_dir / CHECKPOINT_META
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None
