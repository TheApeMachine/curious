import type { CycleRecord } from "../types.js";
import type { ReviewVerdict } from "../review-verdict.js";

const WORKFLOW_BLOCKER =
  /\b(git commit|must commit|branch[- ]?tip|CI artifact|github actions|paste amd64|amd64\+avx|uncommitted.*HEAD|pasted amd64)\b/i;

const META_TASK = /\b(run until done|continuous improvement only|meta roadmap)\b/i;

export interface QualityFlags {
  connectionError: boolean;
  workflowOnlyBlockers: boolean;
  metaTask: boolean;
  overseerIntervened: boolean;
  noisyTrajectory: boolean;
  recurringBlocker: boolean;
}

export function assessQuality(args: {
  failReview: ReviewVerdict;
  taskId: string;
  cyclesToPass: number;
  overseerBetween: boolean;
  sameBlockerRecurred: boolean;
}): { flags: QualityFlags; score: number; rejectReason?: string } {
  const flags: QualityFlags = {
    connectionError: false,
    workflowOnlyBlockers:
      args.failReview.blockingIssues.length > 0 &&
      args.failReview.blockingIssues.every((issue) =>
        WORKFLOW_BLOCKER.test(issue),
      ),
    metaTask: META_TASK.test(args.taskId),
    overseerIntervened: args.overseerBetween,
    noisyTrajectory: args.cyclesToPass > 3,
    recurringBlocker: args.sameBlockerRecurred,
  };

  if (flags.metaTask) {
    return { flags, score: 0, rejectReason: "meta_task" };
  }
  if (flags.workflowOnlyBlockers) {
    return { flags, score: 0, rejectReason: "workflow_only_blockers" };
  }
  if (flags.overseerIntervened) {
    return { flags, score: 0.2, rejectReason: "overseer_intervened" };
  }
  if (flags.noisyTrajectory) {
    return { flags, score: 0.35, rejectReason: "noisy_trajectory" };
  }

  let score = 1;
  if (args.cyclesToPass === 2) {
    score = 0.85;
  } else if (args.cyclesToPass === 3) {
    score = 0.55;
  }
  if (flags.recurringBlocker) {
    score *= 0.5;
  }

  return { flags, score };
}

export function isRecoverableRecord(record: CycleRecord): boolean {
  return record.status === "finished";
}

export function overseerIntervenedBetween(
  history: CycleRecord[],
  fromIndex: number,
  toIndex: number,
): boolean {
  for (let index = fromIndex + 1; index < toIndex; index++) {
    const record = history[index];
    if (record.phase !== "overseer" || record.status !== "finished") {
      continue;
    }
    const summary = record.summary ?? "";
    if (/steering_updated:\s*yes/i.test(summary)) {
      return true;
    }
    if (/OVERALL:\s*(DRIFT|BACKTRACKED)/i.test(summary)) {
      return true;
    }
    if (/spec_adjustments:\s*\n-\s*(?!none)/i.test(summary)) {
      return true;
    }
  }
  return false;
}

export function normalizeBlocker(line: string): string {
  return line.replace(/\s+/g, " ").trim().toLowerCase();
}
