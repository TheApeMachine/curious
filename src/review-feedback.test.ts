import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  findLatestFailedReview,
  formatFailedReviewForDevelop,
  isReviewFail,
} from "./review-feedback.js";
import type { CycleRecord } from "./types.js";
import { REVIEW_FAIL_WORKFLOW_NOTE } from "./workflow-policy.js";

function reviewRecord(
  overrides: Partial<CycleRecord> & Pick<CycleRecord, "cycle" | "runId">,
): CycleRecord {
  return {
    phase: "review",
    status: "finished",
    startedAt: "2026-01-01T00:00:00Z",
    finishedAt: "2026-01-01T00:01:00Z",
    ...overrides,
  };
}

describe("isReviewFail", () => {
  it("returns false for missing or blank summaries", () => {
    assert.equal(isReviewFail(undefined), false);
    assert.equal(isReviewFail(""), false);
    assert.equal(isReviewFail("   \n  "), false);
  });

  it("returns false when OVERALL is PASS", () => {
    const summary = [
      "```review-verdict",
      "OVERALL: PASS",
      "blocking_issues:",
      "-",
      "```",
    ].join("\n");
    assert.equal(isReviewFail(summary), false);
  });

  it("returns true when OVERALL is FAIL", () => {
    const summary = [
      "```review-verdict",
      "OVERALL: FAIL",
      "blocking_issues:",
      "- src/foo.ts: missing tests",
      "```",
    ].join("\n");
    assert.equal(isReviewFail(summary), true);
  });

  it("matches OVERALL: FAIL case-insensitively", () => {
    assert.equal(isReviewFail("OVERALL: fail"), true);
    assert.equal(isReviewFail("overall: FAIL"), true);
  });
});

describe("findLatestFailedReview", () => {
  it("returns undefined for empty history", () => {
    assert.equal(findLatestFailedReview([]), undefined);
  });

  it("returns undefined when no finished review records exist", () => {
    const history: CycleRecord[] = [
      {
        cycle: 1,
        phase: "develop",
        runId: "run-dev",
        status: "finished",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:01:00Z",
      },
      reviewRecord({
        cycle: 1,
        runId: "run-review",
        status: "error",
        summary: "OVERALL: FAIL",
      }),
    ];
    assert.equal(findLatestFailedReview(history), undefined);
  });

  it("returns the latest finished review when it failed", () => {
    const failed = reviewRecord({
      cycle: 3,
      runId: "run-fail",
      summary: "OVERALL: FAIL\nblocking_issues:\n- fix tests",
    });
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "run-pass-old",
        summary: "OVERALL: PASS",
      }),
      failed,
    ];
    assert.equal(findLatestFailedReview(history), failed);
  });

  it("returns undefined when the latest finished review passed", () => {
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "run-fail-old",
        summary: "OVERALL: FAIL",
      }),
      reviewRecord({
        cycle: 2,
        runId: "run-pass",
        summary: "OVERALL: PASS",
      }),
    ];
    assert.equal(findLatestFailedReview(history), undefined);
  });

  it("skips trailing non-review or non-finished records", () => {
    const failed = reviewRecord({
      cycle: 2,
      runId: "run-fail",
      summary: "OVERALL: FAIL",
    });
    const history: CycleRecord[] = [
      failed,
      {
        cycle: 2,
        phase: "sync",
        runId: "run-sync",
        status: "finished",
        startedAt: "2026-01-01T00:02:00Z",
        finishedAt: "2026-01-01T00:03:00Z",
      },
      reviewRecord({
        cycle: 2,
        runId: "run-review-error",
        status: "error",
        summary: "OVERALL: PASS",
      }),
    ];
    assert.equal(findLatestFailedReview(history), failed);
  });
});

describe("formatFailedReviewForDevelop", () => {
  it("formats a failed review with run metadata and workflow note", () => {
    const record = reviewRecord({
      cycle: 4,
      runId: "agent-run-123",
      summary: [
        "```review-verdict",
        "OVERALL: FAIL",
        "blocking_issues:",
        "- src/review-feedback.test.ts: missing",
        "next_develop:",
        "- T1.5",
        "```",
      ].join("\n"),
    });

    const formatted = formatFailedReviewForDevelop(record);

    assert.match(formatted, /^## Review feedback \(FAIL — fix before next review\)/);
    assert.match(formatted, /run `agent-run-123`, cycle 4/);
    assert.match(formatted, /Re-work the \*\*same\*\* task in \*\*## Progress\*\*/);
    assert.match(formatted, new RegExp(REVIEW_FAIL_WORKFLOW_NOTE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    assert.match(formatted, /blocking_issues:\n- src\/review-feedback\.test\.ts: missing/);
    assert.match(formatted, /next_develop:\n- T1\.5/);
  });

  it("uses a placeholder when the review summary is missing", () => {
    const record = reviewRecord({
      cycle: 2,
      runId: "run-empty",
      summary: undefined,
    });

    const formatted = formatFailedReviewForDevelop(record);

    assert.match(formatted, /\(review produced no summary text\)$/);
    assert.doesNotMatch(formatted, /```review-verdict/);
  });
});
