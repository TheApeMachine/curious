import type { Run, SDKMessage } from "@cursor/sdk";

export interface StreamOptions {
  /** Full assistant text + thinking (noisy). */
  verbose?: boolean;
  /** Tool calls, status lines, heartbeats (default on). */
  progress?: boolean;
  onText?: (text: string) => void;
}

const HEARTBEAT_MS = 30_000;

export async function consumeRunStream(
  run: Run,
  options: StreamOptions = {},
): Promise<void> {
  const progress = options.progress !== false;

  if (!run.supports("stream")) {
    if (progress) {
      console.log("[curious] stream not supported; waiting for run to finish…");
    }
    return;
  }

  let lastActivity = Date.now();
  const heartbeat = progress
    ? setInterval(() => {
        const idleSec = Math.round((Date.now() - lastActivity) / 1000);
        console.log(`[curious] still running… (${idleSec}s since last event)`);
      }, HEARTBEAT_MS)
    : undefined;

  try {
    for await (const event of run.stream()) {
      lastActivity = Date.now();
      handleEvent(event, { ...options, progress });
    }
  } finally {
    if (heartbeat) clearInterval(heartbeat);
  }
}

function handleEvent(event: SDKMessage, options: StreamOptions): void {
  const { verbose, progress, onText } = options;

  switch (event.type) {
    case "assistant":
      for (const block of event.message.content) {
        if (block.type === "text") {
          onText?.(block.text);
          if (verbose) process.stdout.write(block.text);
        }
      }
      break;
    case "thinking":
      if (verbose) process.stdout.write(event.text);
      break;
    case "tool_call":
      if (progress || verbose) {
        const detail =
          event.status === "running"
            ? "started"
            : event.status === "completed"
              ? "done"
              : event.status;
        console.log(`[curious] tool ${event.name} (${detail})`);
      }
      break;
    case "status":
      if (progress || verbose) {
        console.log(
          `[curious] status ${event.status}${event.message ? `: ${event.message}` : ""}`,
        );
      }
      break;
    case "task":
      if (progress && event.text) {
        console.log(`[curious] task ${event.status ?? ""}: ${event.text}`);
      }
      break;
    default:
      break;
  }
}
