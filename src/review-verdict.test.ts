import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { extractTaskId, parseReviewVerdict } from "./review-verdict.js";

describe("parseReviewVerdict", () => {
  it("parses a fenced review-verdict block", () => {
    const summary = [
      "Some prose",
      "```review-verdict",
      "OVERALL: FAIL",
      "1_maintainability: PASS",
      "5_verification: FAIL",
      "blocking_issues:",
      "- src/foo.ts:12 — missing test",
      "evidence:",
      "- NOT RUN",
      "next_develop:",
      "- T2.1",
      "```",
    ].join("\n");

    const verdict = parseReviewVerdict(summary);
    assert.ok(verdict);
    assert.equal(verdict.overall, "FAIL");
    assert.equal(verdict.criteria["5_verification"], "FAIL");
    assert.deepEqual(verdict.blockingIssues, ["src/foo.ts:12 — missing test"]);
    assert.equal(verdict.nextDevelop, "T2.1");
  });

  it("returns null when no verdict present", () => {
    assert.equal(parseReviewVerdict("looks fine"), null);
  });
});

describe("extractTaskId", () => {
  it("extracts T and M ids", () => {
    assert.equal(extractTaskId("next: T1.10 — smoke"), "T1.10");
    assert.equal(extractTaskId("M0 complete"), "M0");
    assert.equal(extractTaskId("no id"), undefined);
  });
});
