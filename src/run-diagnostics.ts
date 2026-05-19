import type { ConversationTurn, Run } from "@cursor/sdk";
import {
  formatConversationToolCall,
  type ConversationToolCall,
} from "./tool-call-format.js";

const TAIL_TURNS = 8;
const ERROR_SUMMARY_MAX = 320;

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

  return truncate(firstLine, ERROR_SUMMARY_MAX);
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
  const lines: string[] = [];

  if (run.result) {
    lines.push("--- run.result (full) ---", run.result);
  }

  if (run.supports("conversation")) {
    try {
      const turns = await run.conversation();
      lines.push("--- conversation (tail) ---", formatConversationTail(turns));
    } catch (err) {
      lines.push(
        `--- conversation unavailable: ${err instanceof Error ? err.message : String(err)} ---`,
      );
    }
  } else {
    const reason = run.unsupportedReason("conversation");
    if (reason) {
      lines.push(`--- conversation unsupported: ${reason} ---`);
    }
  }

  if (lines.length === 0) {
    console.error(
      "[curious] run ended with error but no result text or conversation was returned",
    );
    return;
  }

  console.error(lines.join("\n"));
}

function formatConversationTail(turns: ConversationTurn[]): string {
  const slice = turns.slice(-TAIL_TURNS);
  const parts: string[] = [];

  for (const entry of slice) {
    if (entry.type === "shellConversationTurn") {
      const command = entry.turn.shellCommand?.command ?? "(no command)";
      const exitCode = entry.turn.shellOutput?.exitCode;
      const stderr = entry.turn.shellOutput?.stderr?.trim();
      const stdout = entry.turn.shellOutput?.stdout?.trim();
      parts.push(`[shell] ${command} → exit ${exitCode}`);
      if (stderr) parts.push(`  stderr: ${truncate(stderr, 2000)}`);
      if (stdout) parts.push(`  stdout: ${truncate(stdout, 2000)}`);
      continue;
    }

    const userText = entry.turn.userMessage?.text?.trim();
    if (userText) {
      parts.push(`[user] ${truncate(userText, 500)}`);
    }

    for (const step of entry.turn.steps) {
      if (step.type === "assistantMessage") {
        parts.push(`[assistant] ${truncate(step.message.text, 3000)}`);
      } else if (step.type === "thinkingMessage") {
        parts.push(`[thinking] ${truncate(step.message.text, 800)}`);
      } else if (step.type === "toolCall") {
        parts.push(
          `[tool] ${formatConversationToolCall(step.message as ConversationToolCall)}`,
        );
      }
    }
  }

  return parts.length > 0 ? parts.join("\n") : "(empty conversation)";
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}
