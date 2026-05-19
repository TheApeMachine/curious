import { analyzeRoadmap, type RoadmapStatus } from "./spec-roadmap.js";
import type { CuriousState } from "./types.js";

/** At untilDone start: skip the phase loop when every roadmap task is already [x]. */
export function shouldSkipUntilDoneLoop(roadmapStatus: RoadmapStatus): boolean {
  return roadmapStatus.complete;
}

/** After a phase: stop untilDone when sync finished and spec roadmap is complete. */
export function shouldStopUntilDoneAfterPhase(
  state: CuriousState,
  specBody: string,
): boolean {
  const last = state.history[state.history.length - 1];
  if (last?.phase !== "sync" || last.status !== "finished") {
    return false;
  }
  return analyzeRoadmap(specBody).complete;
}
