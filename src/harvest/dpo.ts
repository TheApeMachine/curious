import type { CuriousState } from "../types.js";
import type { CycleRecord } from "../types.js";
import {
  extractTaskId,
  parseReviewVerdict,
  type ReviewVerdict,
} from "../review-verdict.js";
import { isReviewFail } from "../review-feedback.js";
import {
  assessQuality,
  isRecoverableRecord,
  normalizeBlocker,
  overseerIntervenedBetween,
} from "./quality.js";
import {
  gitCommitBefore,
  gitDiffBetween,
  isGitRepository,
} from "./git-join.js";

export interface DpoExample {
  format: "dpo";
  task_id: string;
  prompt: string;
  chosen: string;
  rejected: string;
  rationale: string[];
  quality_score: number;
  reject_reason?: string;
  metadata: {
    fail_cycle: number;
    pass_cycle: number;
    fail_develop_run_id: string;
    pass_develop_run_id: string;
    fail_review_run_id: string;
    pass_review_run_id: string;
    cycles_to_pass: number;
    git?: {
      rejected_sha?: string;
      chosen_sha?: string;
      diff?: string;
    };
    criteria_fail?: string[];
  };
}

export interface HarvestDpoOptions {
  projectRoot: string;
  cwd: string;
  specPath: string;
  minQuality: number;
  includeRejected: boolean;
}

interface IndexedRecord {
  index: number;
  record: CycleRecord;
}

function findDevelopBeforeReview(
  history: CycleRecord[],
  reviewIndex: number,
): IndexedRecord | undefined {
  const review = history[reviewIndex];
  for (let index = reviewIndex - 1; index >= 0; index--) {
    const record = history[index];
    if (record.phase === "develop" && record.cycle === review.cycle) {
      return { index, record };
    }
    if (record.phase === "review" || record.phase === "sync") {
      break;
    }
  }
  for (let index = reviewIndex - 1; index >= 0; index--) {
    const record = history[index];
    if (record.phase === "develop") {
      return { index, record };
    }
  }
  return undefined;
}

function buildPrompt(args: {
  taskId: string;
  specPath: string;
  failReview: ReviewVerdict;
  failDevelop: CycleRecord;
  historyBefore: CycleRecord[];
}): string {
  const historyTail = args.historyBefore
    .slice(-6)
    .map(
      (record) =>
        `- cycle ${record.cycle} ${record.phase} (${record.status}): ${(record.summary ?? "").slice(0, 200).replace(/\n/g, " ")}`,
    )
    .join("\n");

  return [
    `# Develop task ${args.taskId}`,
    "",
    `Spec: ${args.specPath}`,
    "",
    "## Prior orchestrator context",
    historyTail || "(none)",
    "",
    "## Review feedback (FAIL)",
    `blocking_issues:`,
    ...args.failReview.blockingIssues.map((issue) => `- ${issue}`),
    "",
    `evidence:`,
    ...args.failReview.evidence.map((line) => `- ${line}`),
    "",
    "## Previous develop summary",
    args.failDevelop.summary?.trim() ?? "(no summary)",
  ].join("\n");
}

export async function harvestDpoPairs(
  state: CuriousState,
  options: HarvestDpoOptions,
): Promise<DpoExample[]> {
  const history = state.history;
  const examples: DpoExample[] = [];
  const hasGit = await isGitRepository(options.cwd);

  for (let reviewIndex = 0; reviewIndex < history.length; reviewIndex++) {
    const reviewRecord = history[reviewIndex];
    if (
      reviewRecord.phase !== "review" ||
      !isRecoverableRecord(reviewRecord) ||
      !isReviewFail(reviewRecord.summary)
    ) {
      continue;
    }

    const failVerdict = parseReviewVerdict(reviewRecord.summary);
    if (!failVerdict) {
      continue;
    }

    const taskId =
      extractTaskId(failVerdict.nextDevelop) ??
      extractTaskId(reviewRecord.summary);
    if (!taskId) {
      continue;
    }

    const failDevelop = findDevelopBeforeReview(history, reviewIndex);
    if (!failDevelop || !failDevelop.record.summary?.trim()) {
      continue;
    }

    const passMatch = findPassReviewForTask(history, reviewIndex, taskId);
    if (!passMatch) {
      continue;
    }

    const passDevelop = findDevelopBeforeReview(history, passMatch.index);
    if (!passDevelop?.record.summary?.trim()) {
      continue;
    }

    const cyclesToPass = passMatch.record.cycle - reviewRecord.cycle;
    const blockerKey = failVerdict.blockingIssues.map(normalizeBlocker).join("|");
    const sameBlockerRecurred = history
      .slice(reviewIndex + 1, passMatch.index)
      .some((record) => {
        if (record.phase !== "review" || !isReviewFail(record.summary)) {
          return false;
        }
        const verdict = parseReviewVerdict(record.summary);
        if (!verdict) {
          return false;
        }
        const key = verdict.blockingIssues.map(normalizeBlocker).join("|");
        return key === blockerKey && key.length > 0;
      });

    const overseerBetween = overseerIntervenedBetween(
      history,
      reviewIndex,
      passMatch.index,
    );

    const quality = assessQuality({
      failReview: failVerdict,
      taskId,
      cyclesToPass,
      overseerBetween,
      sameBlockerRecurred,
    });

    if (quality.score < options.minQuality && !options.includeRejected) {
      continue;
    }

    const prompt = buildPrompt({
      taskId,
      specPath: options.specPath,
      failReview: failVerdict,
      failDevelop: failDevelop.record,
      historyBefore: history.slice(0, reviewIndex),
    });

    const gitMeta: DpoExample["metadata"]["git"] = {};
    if (hasGit) {
      const rejectedSha = await gitCommitBefore(
        options.cwd,
        failDevelop.record.finishedAt,
      );
      const chosenSha = await gitCommitBefore(
        options.cwd,
        passDevelop.record.finishedAt,
      );
      if (rejectedSha) {
        gitMeta.rejected_sha = rejectedSha;
      }
      if (chosenSha) {
        gitMeta.chosen_sha = chosenSha;
      }
      if (rejectedSha && chosenSha) {
        gitMeta.diff = (await gitDiffBetween(options.cwd, rejectedSha, chosenSha)) ?? undefined;
      }
    }

    const example: DpoExample = {
      format: "dpo",
      task_id: taskId,
      prompt,
      chosen: passDevelop.record.summary!.trim(),
      rejected: failDevelop.record.summary!.trim(),
      rationale: failVerdict.blockingIssues,
      quality_score: quality.score,
      reject_reason: quality.rejectReason,
      metadata: {
        fail_cycle: reviewRecord.cycle,
        pass_cycle: passMatch.record.cycle,
        fail_develop_run_id: failDevelop.record.runId,
        pass_develop_run_id: passDevelop.record.runId,
        fail_review_run_id: reviewRecord.runId,
        pass_review_run_id: passMatch.record.runId,
        cycles_to_pass: cyclesToPass,
        git: Object.keys(gitMeta).length > 0 ? gitMeta : undefined,
        criteria_fail: Object.entries(failVerdict.criteria)
          .filter(([, value]) => value === "FAIL")
          .map(([key]) => key),
      },
    };

    examples.push(example);
  }

  return examples;
}

function findPassReviewForTask(
  history: CycleRecord[],
  afterIndex: number,
  taskId: string,
): IndexedRecord | undefined {
  for (let index = afterIndex + 1; index < history.length; index++) {
    const record = history[index];
    if (record.phase !== "review" || !isRecoverableRecord(record)) {
      continue;
    }
    if (isReviewFail(record.summary)) {
      continue;
    }
    const verdict = parseReviewVerdict(record.summary);
    if (!verdict || verdict.overall !== "PASS") {
      continue;
    }

    const passDevelop = findDevelopBeforeReview(history, index);
    if (!passDevelop) {
      continue;
    }

    const failCycle = history[afterIndex].cycle;
    const developMentionsTask =
      extractTaskId(passDevelop.record.summary) === taskId ||
      Boolean(passDevelop.record.summary?.includes(taskId));

    if (!developMentionsTask && passDevelop.record.cycle > failCycle + 2) {
      continue;
    }

    return { index, record };
  }
  return undefined;
}
