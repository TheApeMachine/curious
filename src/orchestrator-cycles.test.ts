import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  completedCyclesSince,
  retainsPhaseAfterRun,
  shouldAbortCyclesModeOnPhaseError,
  shouldStopAfterRequestedCycles,
  shouldStopAtConfigMaxCycles,
} from "./orchestrator-cycles.js";
import type { CuriousState } from "./types.js";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixturesDir = path.join(repoRoot, "src/test-fixtures");

function stateSnapshot(
  partial: Pick<CuriousState, "phase" | "cycle"> &
    Partial<Pick<CuriousState, "lastError">>,
): CuriousState {
  return {
    version: 1,
    phase: partial.phase,
    cycle: partial.cycle,
    running: false,
    history: [],
    updatedAt: "2026-01-01T00:05:00.000Z",
    lastError: partial.lastError,
  };
}

describe("completedCyclesSince", () => {
  it("returns zero when cycle has not advanced", () => {
    assert.equal(completedCyclesSince(3, 3), 0);
  });

  it("counts full rounds completed since cycleAtStart", () => {
    assert.equal(completedCyclesSince(5, 3), 2);
  });
});

describe("shouldStopAfterRequestedCycles", () => {
  it("returns false when cyclesLimit is undefined", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "develop", cycle: 5 }),
        3,
        undefined,
      ),
      false,
    );
  });

  it("returns false while still mid-cycle (review phase)", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "review", cycle: 4 }),
        3,
        1,
      ),
      false,
    );
  });

  it("returns false while still mid-cycle (sync phase)", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "sync", cycle: 4 }),
        3,
        1,
      ),
      false,
    );
  });

  it("returns false when fewer full cycles completed than the limit", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "develop", cycle: 4 }),
        3,
        2,
      ),
      false,
    );
  });

  it("returns true after one full cycle when limit is 1", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "develop", cycle: 4 }),
        3,
        1,
      ),
      true,
    );
  });

  it("returns true when completed cycles meet a multi-cycle limit", () => {
    assert.equal(
      shouldStopAfterRequestedCycles(
        stateSnapshot({ phase: "develop", cycle: 6 }),
        3,
        3,
      ),
      true,
    );
  });
});

describe("shouldAbortCyclesModeOnPhaseError", () => {
  it("returns false without a cycles limit", () => {
    assert.equal(shouldAbortCyclesModeOnPhaseError(undefined, "boom"), false);
  });

  it("returns false in cycles mode when there is no phase error", () => {
    assert.equal(shouldAbortCyclesModeOnPhaseError(1, undefined), false);
  });

  it("returns true in cycles mode when lastError is set", () => {
    assert.equal(
      shouldAbortCyclesModeOnPhaseError(3, "connection lost"),
      true,
    );
  });
});

describe("shouldStopAtConfigMaxCycles", () => {
  it("returns false when config maxCycles is zero (unlimited)", () => {
    assert.equal(shouldStopAtConfigMaxCycles(99, 0), false);
  });

  it("returns false before the configured cap", () => {
    assert.equal(shouldStopAtConfigMaxCycles(4, 10), false);
  });

  it("returns true when state cycle reaches the cap", () => {
    assert.equal(shouldStopAtConfigMaxCycles(10, 10), true);
  });

  it("returns true when state cycle exceeds the cap", () => {
    assert.equal(shouldStopAtConfigMaxCycles(11, 10), true);
  });
});

describe("retainsPhaseAfterRun", () => {
  it("returns true for error status so the phase can resume", () => {
    assert.equal(retainsPhaseAfterRun("error"), true);
  });

  it("returns true for cancelled status", () => {
    assert.equal(retainsPhaseAfterRun("cancelled"), true);
  });

  it("returns false for finished status so the phase advances", () => {
    assert.equal(retainsPhaseAfterRun("finished"), false);
  });
});

describe("cycles fixtures", () => {
  it("loads a state fixture after one completed cycle (--cycles 1 stop point)", async () => {
    const raw = await readFile(
      path.join(fixturesDir, "state-after-one-cycle.json"),
      "utf8",
    );
    const state = JSON.parse(raw) as CuriousState;

    assert.equal(
      shouldStopAfterRequestedCycles(state, 3, 1),
      true,
      "fixture should represent the --cycles 1 stop boundary",
    );
    assert.equal(shouldAbortCyclesModeOnPhaseError(1, state.lastError), false);
  });

  it("loads a state fixture with phase error for cycles-mode abort", async () => {
    const raw = await readFile(
      path.join(fixturesDir, "state-phase-error-resume.json"),
      "utf8",
    );
    const state = JSON.parse(raw) as CuriousState;

    assert.equal(retainsPhaseAfterRun("error"), true);
    assert.equal(
      shouldAbortCyclesModeOnPhaseError(2, state.lastError),
      true,
    );
    assert.equal(
      shouldStopAfterRequestedCycles(state, 5, 2),
      false,
      "mid-cycle error should not trigger requested-cycles stop",
    );
  });
});
