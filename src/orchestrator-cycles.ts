import type { CuriousState, CycleRecord } from "./types.js";

/** Full develop→review→sync rounds completed since the run started. */
export function completedCyclesSince(
  stateCycle: number,
  cycleAtStart: number,
): number {
  return stateCycle - cycleAtStart;
}

/** Stop after `--cycles N` when N full rounds finished and phase wrapped to develop. */
export function shouldStopAfterRequestedCycles(
  state: Pick<CuriousState, "phase" | "cycle">,
  cycleAtStart: number,
  cyclesLimit: number | undefined,
): boolean {
  if (cyclesLimit === undefined) {
    return false;
  }
  return (
    state.phase === "develop" &&
    completedCyclesSince(state.cycle, cycleAtStart) >= cyclesLimit
  );
}

/** In `--cycles` mode, abort the outer loop when a phase left lastError set. */
export function shouldAbortCyclesModeOnPhaseError(
  cyclesLimit: number | undefined,
  lastError: string | undefined,
): boolean {
  return cyclesLimit !== undefined && lastError !== undefined;
}

/** Stop when config maxCycles is positive and the state cycle reached the cap. */
export function shouldStopAtConfigMaxCycles(
  stateCycle: number,
  configMaxCycles: number,
): boolean {
  return configMaxCycles > 0 && stateCycle >= configMaxCycles;
}

/** Failed or cancelled runs keep the current phase for retry on the next iteration. */
export function retainsPhaseAfterRun(status: CycleRecord["status"]): boolean {
  return status !== "finished";
}
