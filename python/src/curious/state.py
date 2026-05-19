from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from curious.types import CuriousState, Phase

STATE_DIR = ".curious"
STATE_FILE = "state.json"


def state_path(project_root: str | Path) -> Path:
    return Path(project_root) / STATE_DIR / STATE_FILE


def initial_state(phase: Phase = "develop") -> CuriousState:
    return CuriousState(
        phase=phase,
        cycle=0,
        running=False,
        updated_at=_now(),
    )


def load_state(project_root: str | Path) -> CuriousState:
    path = state_path(project_root)
    if not path.is_file():
        return initial_state()
    data = json.loads(path.read_text(encoding="utf-8"))
    return CuriousState.from_json(data)


def save_state(project_root: str | Path, state: CuriousState) -> None:
    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _now()
    path.write_text(
        json.dumps(state.to_json(), indent=2) + "\n",
        encoding="utf-8",
    )


def next_phase(current: Phase) -> Phase:
    if current == "develop":
        return "review"
    if current == "review":
        return "sync"
    if current == "sync":
        return "develop"
    return "develop"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
