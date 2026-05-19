import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { ConversationTurn } from "@cursor/sdk";
import {
  DIAGNOSTIC_TAIL_TURNS,
  ERROR_SUMMARY_MAX,
  formatConversationTail,
  formatConversationUnavailable,
  formatFailureModeHint,
  formatInspectHeader,
  formatRunErrorSummary,
  formatRunFailureTranscript,
  truncateDiagnosticText,
} from "./run-diagnostics.js";

describe("formatRunErrorSummary", () => {
  it("returns undefined for blank result", () => {
    assert.equal(formatRunErrorSummary(undefined), undefined);
    assert.equal(formatRunErrorSummary("   \n  "), undefined);
  });

  it("uses the first non-empty line", () => {
    assert.equal(
      formatRunErrorSummary("line one\nline two"),
      "line one",
    );
  });

  it("truncates long single-line summaries", () => {
    const long = "x".repeat(ERROR_SUMMARY_MAX + 50);
    const summary = formatRunErrorSummary(long);
    assert.ok(summary);
    assert.equal(summary.length, ERROR_SUMMARY_MAX + 1);
    assert.ok(summary.endsWith("…"));
  });
});

describe("truncateDiagnosticText", () => {
  it("returns text unchanged when under the limit", () => {
    assert.equal(truncateDiagnosticText("short", 10), "short");
  });

  it("appends an ellipsis when truncating", () => {
    assert.equal(truncateDiagnosticText("1234567890", 5), "12345…");
  });
});

describe("formatInspectHeader", () => {
  it("includes run id and status", () => {
    assert.equal(
      formatInspectHeader("run-1", "error"),
      "[curious] inspect run-1 status=error",
    );
  });

  it("includes phase, cycle, and truncated lastError", () => {
    const header = formatInspectHeader("run-2", "finished", {
      phase: "review",
      cycle: 7,
      lastError: "ECONNRESET: connection lost during stream",
    });
    assert.match(header, /inspect run-2 status=finished/);
    assert.match(header, /phase=review/);
    assert.match(header, /cycle=7/);
    assert.match(header, /lastError=ECONNRESET/);
  });
});

describe("formatFailureModeHint", () => {
  it("returns undefined for blank messages", () => {
    assert.equal(formatFailureModeHint(undefined), undefined);
  });

  it("hints for transient connection errors", () => {
    const hint = formatFailureModeHint("read ECONNRESET");
    assert.ok(hint);
    assert.match(hint, /Transient connection error/i);
  });

  it("hints for agent busy errors", () => {
    const hint = formatFailureModeHint("Agent already has active run");
    assert.ok(hint);
    assert.match(hint, /active run/i);
  });

  it("hints for missing API key messages", () => {
    const hint = formatFailureModeHint("CURSOR_API_KEY required");
    assert.ok(hint);
    assert.match(hint, /CURSOR_API_KEY/i);
  });

  it("hints when no run id is available", () => {
    const hint = formatFailureModeHint("no run id");
    assert.ok(hint);
    assert.match(hint, /inspect/i);
  });
});

describe("formatConversationUnavailable", () => {
  it("formats fetch errors as a transcript note", () => {
    assert.equal(
      formatConversationUnavailable(new Error("network down")),
      "--- conversation unavailable: network down ---",
    );
  });
});

describe("formatRunFailureTranscript", () => {
  it("returns undefined when there is nothing to show", () => {
    assert.equal(formatRunFailureTranscript({}), undefined);
  });

  it("includes result and conversation sections", () => {
    const transcript = formatRunFailureTranscript({
      result: "boom",
      conversationTail: "[assistant] failed",
    });
    assert.ok(transcript);
    assert.match(transcript, /--- run\.result \(full\) ---/);
    assert.match(transcript, /boom/);
    assert.match(transcript, /--- conversation \(tail\) ---/);
    assert.match(transcript, /\[assistant\] failed/);
  });

  it("includes a conversation note when tail is unavailable", () => {
    const transcript = formatRunFailureTranscript({
      conversationNote: "--- conversation unavailable: timeout ---",
    });
    assert.equal(transcript, "--- conversation unavailable: timeout ---");
  });
});

describe("formatConversationTail", () => {
  it("returns a placeholder for empty history", () => {
    assert.equal(formatConversationTail([]), "(empty conversation)");
  });

  it("formats shell turns with stderr and stdout", () => {
    const turns = [
      {
        type: "shellConversationTurn",
        turn: {
          shellCommand: { command: "npm test" },
          shellOutput: { exitCode: 1, stderr: "FAIL", stdout: "ok" },
        },
      },
    ] as ConversationTurn[];

    const tail = formatConversationTail(turns);
    assert.match(tail, /\[shell\] npm test → exit 1/);
    assert.match(tail, /stderr: FAIL/);
    assert.match(tail, /stdout: ok/);
  });

  it("keeps only the most recent turns", () => {
    const turns = Array.from({ length: DIAGNOSTIC_TAIL_TURNS + 2 }, (_, index) => ({
      type: "shellConversationTurn",
      turn: {
        shellCommand: { command: `cmd-${index}` },
        shellOutput: { exitCode: 0 },
      },
    })) as ConversationTurn[];

    const tail = formatConversationTail(turns);
    assert.doesNotMatch(tail, /cmd-0/);
    assert.doesNotMatch(tail, /cmd-1/);
    assert.match(tail, /cmd-2/);
    assert.match(tail, /cmd-9/);
  });
});
