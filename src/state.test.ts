import path from "node:path";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { initialState, nextPhase, statePath } from "./state.js";
import type { Phase } from "./types.js";

describe("statePath", () => {
  it("joins cwd with .curious/state.json", () => {
    const cwd = "/tmp/my-project";
    assert.equal(statePath(cwd), path.join(cwd, ".curious", "state.json"));
  });

  it("preserves the cwd argument without normalizing trailing slashes", () => {
    const cwd = "/tmp/my-project/";
    assert.equal(statePath(cwd), path.join(cwd, ".curious", "state.json"));
  });

  it("works with relative cwd values", () => {
    assert.equal(statePath("."), path.join(".", ".curious", "state.json"));
  });
});

describe("initialState", () => {
  it("defaults phase to develop", () => {
    const state = initialState();
    assert.equal(state.phase, "develop");
  });

  it("accepts an explicit starting phase", () => {
    const phases: Phase[] = ["develop", "review", "sync", "overseer"];
    for (const phase of phases) {
      assert.equal(initialState(phase).phase, phase);
    }
  });

  it("returns a fresh orchestrator snapshot with empty history", () => {
    const state = initialState("review");
    assert.deepEqual(
      {
        version: state.version,
        phase: state.phase,
        cycle: state.cycle,
        running: state.running,
        history: state.history,
      },
      {
        version: 1,
        phase: "review",
        cycle: 0,
        running: false,
        history: [],
      },
    );
  });

  it("sets updatedAt to an ISO-8601 timestamp", () => {
    const state = initialState();
    assert.match(state.updatedAt, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  });
});

describe("nextPhase", () => {
  it("advances develop to review", () => {
    assert.equal(nextPhase("develop"), "review");
  });

  it("advances review to sync", () => {
    assert.equal(nextPhase("review"), "sync");
  });

  it("wraps sync back to develop", () => {
    assert.equal(nextPhase("sync"), "develop");
  });

  it("returns develop after overseer", () => {
    assert.equal(nextPhase("overseer"), "develop");
  });
});
