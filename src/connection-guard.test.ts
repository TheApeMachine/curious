import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  maxTransientRetriesPerPhase,
  transientRetryDelayMs,
} from "./connection-guard.js";

describe("maxTransientRetriesPerPhase", () => {
  it("returns the per-phase transient retry budget", () => {
    assert.equal(maxTransientRetriesPerPhase(), 12);
  });
});

describe("transientRetryDelayMs", () => {
  it("starts at 15s for the first retry attempt", () => {
    assert.equal(transientRetryDelayMs(0), 15_000);
  });

  it("doubles delay for successive attempts up to the cap", () => {
    assert.equal(transientRetryDelayMs(1), 30_000);
    assert.equal(transientRetryDelayMs(2), 60_000);
  });

  it("caps delay at 2 minutes", () => {
    assert.equal(transientRetryDelayMs(3), 120_000);
    assert.equal(transientRetryDelayMs(4), 120_000);
    assert.equal(transientRetryDelayMs(99), 120_000);
  });
});
