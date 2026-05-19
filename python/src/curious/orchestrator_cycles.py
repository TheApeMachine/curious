from __future__ import annotations

from curious.types import CuriousState


def completed_cycles_since(state_cycle: int, cycle_at_start: int) -> int:
    return state_cycle - cycle_at_start


def should_stop_after_requested_cycles(
    state: CuriousState, cycle_at_start: int, cycles_limit: int | None
) -> bool:
    if cycles_limit is None:
        return False
    return (
        state.phase == "develop"
        and completed_cycles_since(state.cycle, cycle_at_start) >= cycles_limit
    )


def should_abort_cycles_mode_on_phase_error(
    cycles_limit: int | None, last_error: str | None
) -> bool:
    return cycles_limit is not None and last_error is not None


def should_stop_at_config_max_cycles(state_cycle: int, config_max_cycles: int) -> bool:
    return config_max_cycles > 0 and state_cycle >= config_max_cycles
