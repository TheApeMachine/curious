/** Tool call payload from conversation history (discriminated by `type`, not `name`). */
export interface ConversationToolCall {
  type: string;
  args?: Record<string, unknown>;
  result?: { status?: string };
}

export function formatConversationToolCall(message: ConversationToolCall): string {
  const status =
    message.result?.status === "success"
      ? "completed"
      : message.result?.status === "error"
        ? "error"
        : message.result
          ? message.result.status ?? "done"
          : "running";

  const hint = toolCallHint(message);
  return hint ? `${message.type} — ${hint} (${status})` : `${message.type} (${status})`;
}

function toolCallHint(message: ConversationToolCall): string | undefined {
  const args = message.args;
  if (!args || typeof args !== "object") {
    return undefined;
  }

  if (message.type === "shell" && typeof args.command === "string") {
    return truncateOneLine(args.command, 72);
  }

  if (typeof args.path === "string") {
    return truncateOneLine(args.path, 72);
  }

  if (typeof args.pattern === "string") {
    return truncateOneLine(args.pattern, 72);
  }

  if (typeof args.globPattern === "string") {
    return truncateOneLine(args.globPattern, 72);
  }

  if (typeof args.description === "string") {
    return truncateOneLine(args.description, 72);
  }

  return undefined;
}

function truncateOneLine(text: string, max: number): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  if (oneLine.length <= max) return oneLine;
  return `${oneLine.slice(0, max)}…`;
}
