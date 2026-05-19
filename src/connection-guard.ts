import type { Run } from "@cursor/sdk";
import { errorMessage, isTransientError } from "./transient-errors.js";

export interface ConnectionGuard {
  abort: AbortController;
  dispose: () => void;
}

const MAX_TRANSIENT_RETRIES_PER_PHASE = 12;

/** Backoff after connection loss: 15s, 30s, 60s, … capped at 2 min. */
export function transientRetryDelayMs(attempt: number): number {
  const base = 15_000;
  const capped = Math.min(attempt, 4);
  return Math.min(120_000, base * 2 ** capped);
}

export function maxTransientRetriesPerPhase(): number {
  return MAX_TRANSIENT_RETRIES_PER_PHASE;
}

/**
 * Catches stray ECONNRESET rejections from the SDK while the orchestrator loop runs.
 * Per-run guards only live for one phase attempt; this covers tailers that outlive them.
 */
export function installOrchestratorNetworkGuard(
  isActive: () => boolean,
): () => void {
  const onRejection = (reason: unknown) => {
    if (!isActive() || !isTransientError(reason)) {
      return;
    }
    console.error(
      `[curious] background connection error (suppressed): ${errorMessage(reason)}`,
    );
  };

  process.on("unhandledRejection", onRejection);

  return () => {
    process.off("unhandledRejection", onRejection);
  };
}

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
