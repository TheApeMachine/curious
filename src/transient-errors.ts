import { Code, ConnectError } from "@connectrpc/connect";
import { AgentBusyError, CursorAgentError } from "@cursor/sdk";

const TRANSIENT_CONNECT_CODES = new Set([
  Code.Unavailable,
  Code.DeadlineExceeded,
  Code.ResourceExhausted,
  Code.Aborted,
  Code.Internal,
]);

const TRANSIENT_ERRNO = new Set([
  "ECONNRESET",
  "ETIMEDOUT",
  "ECONNREFUSED",
  "EPIPE",
  "ENOTFOUND",
  "EAI_AGAIN",
]);

const TRANSIENT_MESSAGE = /ECONNRESET|ETIMEDOUT|socket hang up|network error/i;

/** Errors where retrying the same phase is reasonable. */
export function isTransientError(err: unknown): boolean {
  if (err instanceof CursorAgentError) {
    return err.isRetryable;
  }

  if (err instanceof ConnectError) {
    return TRANSIENT_CONNECT_CODES.has(err.code);
  }

  if (err && typeof err === "object") {
    const errno = (err as NodeJS.ErrnoException).code;
    if (errno && TRANSIENT_ERRNO.has(errno)) {
      return true;
    }

    const cause = (err as { cause?: unknown }).cause;
    if (cause && cause !== err) {
      return isTransientError(cause);
    }
  }

  const message = err instanceof Error ? err.message : String(err);
  return TRANSIENT_MESSAGE.test(message);
}

/** Local agent still has a run from a crashed or abandoned orchestrator session. */
export function isAgentBusyError(err: unknown): boolean {
  if (err instanceof AgentBusyError) {
    return true;
  }
  return /already has active run/i.test(errorMessage(err));
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}
