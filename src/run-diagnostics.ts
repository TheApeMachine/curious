import type { ConversationTurn, Run } from "@cursor/sdk";

const TAIL_TURNS = 8;

export async function logRunFailure(run: Run): Promise<void> {
  const lines: string[] = [];

  if (run.result) {
    lines.push("--- run.result ---", run.result);
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
        const toolCall = step.message as { name?: string; status?: string };
        parts.push(
          `[tool] ${toolCall.name ?? "unknown"} (${toolCall.status ?? "?"})`,
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
