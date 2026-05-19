import type { Run, SDKMessage } from "@cursor/sdk";
import { errorMessage } from "./transient-errors.js";

export interface StreamOptions {
  /** Full assistant text + thinking (noisy). */
  verbose?: boolean;
  /** Tool calls, status lines, heartbeats (default on). */
  progress?: boolean;
  onText?: (text: string) => void;
  /** When aborted (e.g. connection loss), the stream consumer rejects. */
  signal?: AbortSignal;
}

const HEARTBEAT_MS = 30_000;

function throwIfAborted(signal?: AbortSignal): void {
  if (!signal?.aborted) return;
  const reason = signal.reason;
  throw reason instanceof Error ? reason : new Error(errorMessage(reason));
}

async function nextStreamEvent<T>(
  promise: Promise<IteratorResult<T>>,
  signal?: AbortSignal,
): Promise<IteratorResult<T>> {
  if (!signal) {
    return promise;
  }

  return new Promise((resolve, reject) => {
    const onAbort = () => {
      const reason = signal.reason;
      reject(reason instanceof Error ? reason : new Error(errorMessage(reason)));
    };

    if (signal.aborted) {
      onAbort();
      return;
    }

    signal.addEventListener("abort", onAbort, { once: true });

    promise.then(
      (value) => {
        signal.removeEventListener("abort", onAbort);
        if (signal.aborted) {
          onAbort();
          return;
        }
        resolve(value);
      },
      (err) => {
        signal.removeEventListener("abort", onAbort);
        reject(err);
      },
    );
  });
}

export async function consumeRunStream(
  run: Run,
  options: StreamOptions = {},
): Promise<void> {
  const progress = options.progress !== false;
  const { signal } = options;

  if (!run.supports("stream")) {
    if (progress) {
      console.log("[curious] stream not supported; waiting for run to finish…");
    }
    return;
  }

  let lastActivity = Date.now();
  const heartbeat = progress
    ? setInterval(() => {
        throwIfAborted(signal);
        const idleSec = Math.round((Date.now() - lastActivity) / 1000);
        console.log(`[curious] still running… (${idleSec}s since last event)`);
      }, HEARTBEAT_MS)
    : undefined;

  const iterator = run.stream()[Symbol.asyncIterator]();

  try {
    while (true) {
      throwIfAborted(signal);
      const { done, value } = await nextStreamEvent(iterator.next(), signal);
      if (done) break;
      lastActivity = Date.now();
      handleEvent(value, { ...options, progress });
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
