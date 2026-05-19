import type { Run } from "@cursor/sdk";
import { errorMessage, isTransientError } from "./transient-errors.js";

export interface ConnectionGuard {
  /** Abort the stream consumer when the SDK connection drops. */
  abort: AbortController;
  dispose: () => void;
}

/**
 * Background SDK traffic (stream tailer, status polling) can reject with
 * ECONNRESET without rejecting the stream iterator. Cancel the run and abort
 * local consumers so the orchestrator can retry the same phase.
 */
export function installConnectionGuard(
  run: Run,
  onConnectionLost?: () => void,
): ConnectionGuard {
  const abort = new AbortController();
  let disposed = false;

  const onRejection = (reason: unknown) => {
    if (disposed || !isTransientError(reason)) {
      return;
    }
    console.error(
      `[curious] connection lost during ${run.id}: ${errorMessage(reason)} — recovering`,
    );
    onConnectionLost?.();
    const error =
      reason instanceof Error ? reason : new Error(errorMessage(reason));
    abort.abort(error);
    void run.cancel().catch(() => {});
  };

  process.on("unhandledRejection", onRejection);

  return {
    abort,
    dispose: () => {
      disposed = true;
      process.off("unhandledRejection", onRejection);
    },
  };
}
