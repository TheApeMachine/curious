import type { ConversationTurn, Run } from "@cursor/sdk";
import {
  errorMessage,
  isAgentBusyError,
  isTransientError,
} from "./transient-errors.js";
import {
  formatConversationToolCall,
  type ConversationToolCall,
} from "./tool-call-format.js";

export const DIAGNOSTIC_TAIL_TURNS = 8;
export const ERROR_SUMMARY_MAX = 320;

/** One-line excerpt from `run.result` for failed runs. */
export function formatRunErrorSummary(result?: string): string | undefined {
  if (!result?.trim()) {
    return undefined;
  }

  const text = result.trim();
  const firstLine = text.split("\n").find((line) => line.trim())?.trim();
  if (!firstLine) {
    return undefined;
  }

  return truncateDiagnosticText(firstLine, ERROR_SUMMARY_MAX);
}

export function truncateDiagnosticText(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

/** Header line for `curious inspect`. */
export function formatInspectHeader(
  runId: string,
  status: string,
  context?: {
    phase?: string;
    cycle?: number;
    lastError?: string;
  },
): string {
  const parts = [`[curious] inspect ${runId} status=${status}`];
  if (context?.phase !== undefined) {
    parts.push(`phase=${context.phase}`);
  }
  if (context?.cycle !== undefined) {
    parts.push(`cycle=${context.cycle}`);
  }
  if (context?.lastError?.trim()) {
    parts.push(`lastError=${truncateDiagnosticText(context.lastError.trim(), 120)}`);
  }
  return parts.join(" ");
}

/** Actionable hint for common orchestrator failure messages. */
export function formatFailureModeHint(message?: string): string | undefined {
  if (!message?.trim()) {
    return undefined;
  }

  const err = new Error(message.trim());
  if (isAgentBusyError(err)) {
    return "Agent still has an active run — re-run the phase; orchestrator may retry with force.";
  }
  if (isTransientError(err)) {
    return "Transient connection error — re-run the same phase; orchestrator retries with backoff.";
  }
  if (/CURSOR_API_KEY|api key/i.test(message)) {
    return "Set CURSOR_API_KEY in the environment or curious.config.json.";
  }
  if (/no run id|agent id/i.test(message)) {
    return "Run a develop/review/sync phase first, or pass an explicit run id to inspect.";
  }
  return undefined;
}

export function formatConversationUnavailable(err: unknown): string {
  return `--- conversation unavailable: ${errorMessage(err)} ---`;
}

export interface RunFailureSnapshot {
  result?: string;
  conversationTail?: string;
  conversationNote?: string;
}

/** Assemble failure transcript sections without calling the SDK. */
export function formatRunFailureTranscript(
  snapshot: RunFailureSnapshot,
): string | undefined {
  const lines: string[] = [];

  if (snapshot.result) {
    lines.push("--- run.result (full) ---", snapshot.result);
  }

  if (snapshot.conversationTail !== undefined) {
    lines.push("--- conversation (tail) ---", snapshot.conversationTail);
  } else if (snapshot.conversationNote) {
    lines.push(snapshot.conversationNote);
  }

  return lines.length > 0 ? lines.join("\n") : undefined;
}

function printRunErrorSummary(run: Run): void {
  const summary = formatRunErrorSummary(run.result);
  if (summary) {
    console.error(`[curious] error reason: ${summary}`);
    return;
  }
  console.error(
    "[curious] run ended with error (no result message — see transcript below)",
  );
}

/** One-line reason plus full transcript (conversation tail, run.result). */
export async function logRunErrorDetails(run: Run): Promise<void> {
  printRunErrorSummary(run);
  await logRunFailure(run);
}

export async function logRunFailure(run: Run): Promise<void> {
  const snapshot: RunFailureSnapshot = {};

  if (run.result) {
    snapshot.result = run.result;
  }

  if (run.supports("conversation")) {
    try {
      const turns = await run.conversation();
      snapshot.conversationTail = formatConversationTail(turns);
    } catch (err) {
      snapshot.conversationNote = formatConversationUnavailable(err);
    }
  } else {
    const reason = run.unsupportedReason("conversation");
    if (reason) {
      snapshot.conversationNote = `--- conversation unsupported: ${reason} ---`;
    }
  }

  const transcript = formatRunFailureTranscript(snapshot);
  if (!transcript) {
    console.error(
      "[curious] run ended with error but no result text or conversation was returned",
    );
    return;
  }

  console.error(transcript);
}

export function formatConversationTail(turns: ConversationTurn[]): string {
  const slice = turns.slice(-DIAGNOSTIC_TAIL_TURNS);
  const parts: string[] = [];

  for (const entry of slice) {
    if (entry.type === "shellConversationTurn") {
      const command = entry.turn.shellCommand?.command ?? "(no command)";
      const exitCode = entry.turn.shellOutput?.exitCode;
      const stderr = entry.turn.shellOutput?.stderr?.trim();
      const stdout = entry.turn.shellOutput?.stdout?.trim();
      parts.push(`[shell] ${command} → exit ${exitCode}`);
      if (stderr) parts.push(`  stderr: ${truncateDiagnosticText(stderr, 2000)}`);
      if (stdout) parts.push(`  stdout: ${truncateDiagnosticText(stdout, 2000)}`);
      continue;
    }

    const userText = entry.turn.userMessage?.text?.trim();
    if (userText) {
      parts.push(`[user] ${truncateDiagnosticText(userText, 500)}`);
    }

    for (const step of entry.turn.steps) {
      if (step.type === "assistantMessage") {
        parts.push(`[assistant] ${truncateDiagnosticText(step.message.text, 3000)}`);
      } else if (step.type === "thinkingMessage") {
        parts.push(`[thinking] ${truncateDiagnosticText(step.message.text, 800)}`);
      } else if (step.type === "toolCall") {
        parts.push(
          `[tool] ${formatConversationToolCall(step.message as ConversationToolCall)}`,
        );
      }
    }
  }

  return parts.length > 0 ? parts.join("\n") : "(empty conversation)";
}
