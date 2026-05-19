import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { CuriousState } from "../types.js";
import { harvestDpoPairs } from "./dpo.js";

function finished(
  partial: Pick<
    import("../types.js").CycleRecord,
    "cycle" | "phase" | "runId" | "summary"
  >,
): import("../types.js").CycleRecord {
  return {
    status: "finished",
    startedAt: "2026-01-01T00:00:00Z",
    finishedAt: "2026-01-01T00:05:00Z",
    ...partial,
  };
}

describe("harvestDpoPairs", () => {
  it("emits a DPO pair for FAIL then PASS on the same task", async () => {
    const state: CuriousState = {
      version: 1,
      phase: "develop",
      cycle: 2,
      running: false,
      history: [
        finished({
          cycle: 1,
          phase: "develop",
          runId: "run-dev-fail",
          summary: "## T2.1 develop\nbroken kernel",
        }),
        finished({
          cycle: 1,
          phase: "review",
          runId: "run-rev-fail",
          summary: [
            "```review-verdict",
            "OVERALL: FAIL",
            "5_verification: FAIL",
            "blocking_issues:",
            "- pkg/foo.s:12 — unmasked tail",
            "next_develop:",
            "- T2.1",
            "```",
          ].join("\n"),
        }),
        finished({
          cycle: 2,
          phase: "develop",
          runId: "run-dev-pass",
          summary: "## T2.1 fix\nmasked tail in pkg/foo.s",
        }),
        finished({
          cycle: 2,
          phase: "review",
          runId: "run-rev-pass",
          summary: [
            "```review-verdict",
            "OVERALL: PASS",
            "blocking_issues:",
            "-",
            "next_develop:",
            "- T2.2",
            "```",
          ].join("\n"),
        }),
      ],
      updatedAt: "2026-01-01T00:00:00Z",
    };

    const pairs = await harvestDpoPairs(state, {
      projectRoot: process.cwd(),
      cwd: process.cwd(),
      specPath: "spec/SPEC.md",
      minQuality: 0,
      includeRejected: true,
    });

    assert.equal(pairs.length, 1);
    assert.equal(pairs[0].task_id, "T2.1");
    assert.match(pairs[0].rejected, /broken kernel/);
    assert.match(pairs[0].chosen, /masked tail/);
    assert.deepEqual(pairs[0].rationale, ["pkg/foo.s:12 — unmasked tail"]);
  });

  it("skips error records", async () => {
    const state: CuriousState = {
      version: 1,
      phase: "develop",
      cycle: 0,
      running: false,
      history: [
        {
          cycle: 0,
          phase: "develop",
          runId: "run-err",
          status: "error",
          startedAt: "2026-01-01T00:00:00Z",
          finishedAt: "2026-01-01T00:01:00Z",
        },
      ],
      updatedAt: "2026-01-01T00:00:00Z",
    };

    const pairs = await harvestDpoPairs(state, {
      projectRoot: process.cwd(),
      cwd: process.cwd(),
      specPath: "spec/SPEC.md",
      minQuality: 0,
      includeRejected: true,
    });

    assert.equal(pairs.length, 0);
  });
});
