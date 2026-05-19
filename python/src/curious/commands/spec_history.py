from __future__ import annotations

from curious.config import resolve_config
from curious.spec_history import correlate_overseer_edits, load_overseer_labels
from curious.state import load_state


def run_spec_history_correlate(config_path: str | None) -> None:
    config = resolve_config(config_path=config_path, require_spec=False)
    state = load_state(config.project_root)
    labels = load_overseer_labels(config.project_root)
    if not labels:
        print("[curious] no overseer labels in .curious/spec_history/labels.jsonl")
        return
    results = correlate_overseer_edits(state.history, labels)
    print("[curious] overseer edit correlation (top helpful → harmful):")
    for row in results[:5]:
        before = row["before_pass_rate"]
        after = row["after_pass_rate"]
        print(
            f"  cycle {row['cycle']}: before={before} after={after} "
            f"(+{row['lines_added']} lines) {row['summary'][:80]}"
        )
    if len(results) > 5:
        print(f"  … and {len(results) - 5} more")
