import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { analyzeRoadmap } from "./spec-roadmap.js";
import {
  shouldSkipUntilDoneLoop,
  shouldStopUntilDoneAfterPhase,
} from "./orchestrator-roadmap.js";
import type { CuriousState, CycleRecord } from "./types.js";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixturesDir = path.join(repoRoot, "src/test-fixtures");

function syncRecord(cycle: number, status: CycleRecord["status"] = "finished"): CycleRecord {
  return {
    cycle,
    phase: "sync",
    runId: `run-sync-${cycle}`,
    status,
    startedAt: "2026-01-01T00:00:00.000Z",
    finishedAt: "2026-01-01T00:05:00.000Z",
  };
}

function stateWithHistory(history: CycleRecord[]): CuriousState {
  const last = history[history.length - 1];
  return {
    version: 1,
    phase: last?.phase === "sync" ? "develop" : "review",
    cycle: last?.cycle ?? 0,
    running: false,
    history,
    updatedAt: "2026-01-01T00:05:00.000Z",
  };
}

describe("shouldSkipUntilDoneLoop", () => {
  it("returns true when every roadmap task is checked", () => {
    const spec = [
      "## Roadmap",
      "",
      "- [x] T1.1 — done",
      "- [x] T1.2 — done",
    ].join("\n");

    assert.equal(shouldSkipUntilDoneLoop(analyzeRoadmap(spec)), true);
  });

  it("returns false when roadmap still has unchecked tasks", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n- [ ] T1.2 — pending\n";
    assert.equal(shouldSkipUntilDoneLoop(analyzeRoadmap(spec)), false);
  });

  it("returns false when roadmap has no T*/M* tasks", () => {
    const spec = "## Roadmap\n\n_No tasks yet._\n";
    assert.equal(shouldSkipUntilDoneLoop(analyzeRoadmap(spec)), false);
  });
});

describe("shouldStopUntilDoneAfterPhase", () => {
  it("returns false when history is empty", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n";
    assert.equal(
      shouldStopUntilDoneAfterPhase(stateWithHistory([]), spec),
      false,
    );
  });

  it("returns false when the last finished phase is not sync", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n";
    const state = stateWithHistory([
      {
        cycle: 1,
        phase: "review",
        runId: "run-review-1",
        status: "finished",
        startedAt: "2026-01-01T00:00:00.000Z",
        finishedAt: "2026-01-01T00:05:00.000Z",
      },
    ]);

    assert.equal(shouldStopUntilDoneAfterPhase(state, spec), false);
  });

  it("returns false when sync did not finish successfully", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n";
    const state = stateWithHistory([syncRecord(1, "error")]);

    assert.equal(shouldStopUntilDoneAfterPhase(state, spec), false);
  });

  it("returns false when sync finished but roadmap still has unchecked tasks", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n- [ ] T1.2 — pending\n";
    const state = stateWithHistory([syncRecord(1)]);

    assert.equal(shouldStopUntilDoneAfterPhase(state, spec), false);
  });

  it("returns true when sync finished and every roadmap task is checked", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n- [x] T1.2 — done\n";
    const state = stateWithHistory([syncRecord(3)]);

    assert.equal(shouldStopUntilDoneAfterPhase(state, spec), true);
  });

  it("uses the last history entry only", () => {
    const spec = "## Roadmap\n\n- [x] T1.1 — done\n";
    const state = stateWithHistory([
      syncRecord(2),
      {
        cycle: 3,
        phase: "develop",
        runId: "run-dev-3",
        status: "finished",
        startedAt: "2026-01-01T00:00:00.000Z",
        finishedAt: "2026-01-01T00:05:00.000Z",
      },
    ]);

    assert.equal(shouldStopUntilDoneAfterPhase(state, spec), false);
  });
});

describe("untilDone fixtures", () => {
  it("loads a complete-roadmap spec fixture for early-exit at start", async () => {
    const spec = await readFile(
      path.join(fixturesDir, "roadmap-complete.spec.md"),
      "utf8",
    );
    assert.equal(shouldSkipUntilDoneLoop(analyzeRoadmap(spec)), true);
    assert.equal(shouldStopUntilDoneAfterPhase(stateWithHistory([]), spec), false);
  });

  it("loads an incomplete-roadmap spec fixture for mid-run continuation", async () => {
    const spec = await readFile(
      path.join(fixturesDir, "roadmap-incomplete.spec.md"),
      "utf8",
    );
    assert.equal(shouldSkipUntilDoneLoop(analyzeRoadmap(spec)), false);
    assert.equal(
      shouldStopUntilDoneAfterPhase(stateWithHistory([syncRecord(1)]), spec),
      false,
    );
  });

  it("detects untilDone stop after final sync on the complete fixture", async () => {
    const spec = await readFile(
      path.join(fixturesDir, "roadmap-complete.spec.md"),
      "utf8",
    );
    assert.equal(
      shouldStopUntilDoneAfterPhase(stateWithHistory([syncRecord(5)]), spec),
      true,
    );
  });
});
