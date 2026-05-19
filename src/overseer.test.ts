import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  countTrailingReviewFails,
  formatHistoryForOverseer,
  shouldRunOverseer,
} from "./overseer.js";
import type { CuriousConfig, CuriousState, CycleRecord } from "./types.js";

function testConfig(overrides: Partial<CuriousConfig> = {}): CuriousConfig {
  return {
    specPath: "/tmp/spec/SPEC.md",
    cwd: "/tmp/project",
    runtime: "local",
    model: { id: "composer-2.5" },
    cycleDelayMs: 0,
    maxCycles: 0,
    overseerEveryNCycles: 5,
    overseerOnReviewFailStreak: 2,
    ...overrides,
  };
}

function testState(overrides: Partial<CuriousState> = {}): CuriousState {
  return {
    version: 1,
    phase: "sync",
    cycle: 0,
    running: false,
    history: [],
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

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

describe("shouldRunOverseer", () => {
  it("returns false when both interval and fail streak are disabled", () => {
    const state = testState({ cycle: 10 });
    const config = testConfig({
      overseerEveryNCycles: 0,
      overseerOnReviewFailStreak: 0,
    });
    assert.equal(shouldRunOverseer(state, config), false);
  });

  it("returns true when cycle is a positive multiple of the interval", () => {
    const state = testState({ cycle: 10 });
    const config = testConfig({
      overseerEveryNCycles: 5,
      overseerOnReviewFailStreak: 0,
    });
    assert.equal(shouldRunOverseer(state, config), true);
  });

  it("returns false when cycle is zero even if interval would match", () => {
    const state = testState({ cycle: 0 });
    const config = testConfig({
      overseerEveryNCycles: 5,
      overseerOnReviewFailStreak: 0,
    });
    assert.equal(shouldRunOverseer(state, config), false);
  });

  it("returns false when cycle is not on the interval boundary", () => {
    const state = testState({ cycle: 7 });
    const config = testConfig({
      overseerEveryNCycles: 5,
      overseerOnReviewFailStreak: 0,
    });
    assert.equal(shouldRunOverseer(state, config), false);
  });

  it("returns true when trailing review fails meet the streak threshold", () => {
    const state = testState({
      cycle: 3,
      history: [
        reviewRecord({
          cycle: 2,
          runId: "fail-1",
          summary: "OVERALL: FAIL",
        }),
        reviewRecord({
          cycle: 3,
          runId: "fail-2",
          summary: "OVERALL: FAIL",
        }),
      ],
    });
    const config = testConfig({
      overseerEveryNCycles: 0,
      overseerOnReviewFailStreak: 2,
    });
    assert.equal(shouldRunOverseer(state, config), true);
  });

  it("returns false when trailing review fails are below the streak threshold", () => {
    const state = testState({
      history: [
        reviewRecord({
          cycle: 1,
          runId: "fail-1",
          summary: "OVERALL: FAIL",
        }),
      ],
    });
    const config = testConfig({
      overseerEveryNCycles: 0,
      overseerOnReviewFailStreak: 2,
    });
    assert.equal(shouldRunOverseer(state, config), false);
  });
});

describe("countTrailingReviewFails", () => {
  it("returns zero for empty history", () => {
    assert.equal(countTrailingReviewFails([]), 0);
  });

  it("counts consecutive trailing finished review FAIL records", () => {
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "pass-old",
        summary: "OVERALL: PASS",
      }),
      reviewRecord({
        cycle: 2,
        runId: "fail-1",
        summary: "OVERALL: FAIL",
      }),
      reviewRecord({
        cycle: 3,
        runId: "fail-2",
        summary: "OVERALL: FAIL",
      }),
    ];
    assert.equal(countTrailingReviewFails(history), 2);
  });

  it("stops at a trailing non-review record", () => {
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "fail-old",
        summary: "OVERALL: FAIL",
      }),
      {
        cycle: 2,
        phase: "sync",
        runId: "sync",
        status: "finished",
        startedAt: "2026-01-01T00:02:00Z",
        finishedAt: "2026-01-01T00:03:00Z",
      },
    ];
    assert.equal(countTrailingReviewFails(history), 0);
  });

  it("stops at a trailing review that did not finish", () => {
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "fail-old",
        summary: "OVERALL: FAIL",
      }),
      reviewRecord({
        cycle: 2,
        runId: "review-error",
        status: "error",
        summary: "OVERALL: FAIL",
      }),
    ];
    assert.equal(countTrailingReviewFails(history), 0);
  });

  it("stops at the first trailing PASS review", () => {
    const history: CycleRecord[] = [
      reviewRecord({
        cycle: 1,
        runId: "fail-old",
        summary: "OVERALL: FAIL",
      }),
      reviewRecord({
        cycle: 2,
        runId: "pass",
        summary: "OVERALL: PASS",
      }),
      reviewRecord({
        cycle: 3,
        runId: "fail-new",
        summary: "OVERALL: FAIL",
      }),
    ];
    assert.equal(countTrailingReviewFails(history), 1);
  });
});

describe("formatHistoryForOverseer", () => {
  it("returns a placeholder when history is empty", () => {
    assert.equal(formatHistoryForOverseer([]), "(no prior runs recorded)");
  });

  it("formats a markdown table with cycle, phase, status, and summary", () => {
    const history: CycleRecord[] = [
      {
        cycle: 4,
        phase: "develop",
        runId: "run-dev",
        status: "finished",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:01:00Z",
        summary: "Implemented T1.9 tests",
      },
    ];

    const formatted = formatHistoryForOverseer(history);

    assert.match(formatted, /^\| Cycle \| Phase \| Status \| Summary \|/);
    assert.match(formatted, /\| 4 \| develop \| finished \| Implemented T1\.9 tests \|/);
  });

  it("escapes pipes and collapses newlines in summaries", () => {
    const history: CycleRecord[] = [
      {
        cycle: 1,
        phase: "review",
        runId: "run-review",
        status: "finished",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:01:00Z",
        summary: "line one\nline two | with pipe",
      },
    ];

    const formatted = formatHistoryForOverseer(history);

    assert.match(formatted, /line one line two \\| with pipe/);
    assert.doesNotMatch(formatted, /\nline two/);
  });

  it("truncates long summaries to 200 characters", () => {
    const longSummary = "x".repeat(250);
    const history: CycleRecord[] = [
      {
        cycle: 1,
        phase: "sync",
        runId: "run-sync",
        status: "finished",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:01:00Z",
        summary: longSummary,
      },
    ];

    const formatted = formatHistoryForOverseer(history);
    const row = formatted.split("\n").at(-1);

    assert.ok(row);
    assert.match(row, /\| 1 \| sync \| finished \| x{200} \|/);
    assert.doesNotMatch(row, /x{201}/);
  });

  it("uses a dash when summary is missing", () => {
    const history: CycleRecord[] = [
      {
        cycle: 2,
        phase: "overseer",
        runId: "run-overseer",
        status: "error",
        startedAt: "2026-01-01T00:00:00Z",
        finishedAt: "2026-01-01T00:01:00Z",
      },
    ];

    const formatted = formatHistoryForOverseer(history);

    assert.match(formatted, /\| 2 \| overseer \| error \| — \|/);
  });

  it("includes only the most recent 40 records", () => {
    const history: CycleRecord[] = Array.from({ length: 45 }, (_, index) => ({
      cycle: index + 1,
      phase: "develop" as const,
      runId: `run-${index + 1}`,
      status: "finished" as const,
      startedAt: "2026-01-01T00:00:00Z",
      finishedAt: "2026-01-01T00:01:00Z",
      summary: `cycle ${index + 1}`,
    }));

    const formatted = formatHistoryForOverseer(history);
    const dataRows = formatted.split("\n").slice(2);

    assert.equal(dataRows.length, 40);
    assert.match(formatted, /\| 6 \| develop \| finished \| cycle 6 \|/);
    assert.match(formatted, /\| 45 \| develop \| finished \| cycle 45 \|/);
    assert.doesNotMatch(formatted, /\| 5 \| develop \| finished \| cycle 5 \|/);
  });
});
