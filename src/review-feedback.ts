import type { CycleRecord } from "./types.js";

export function isReviewFail(summary?: string): boolean {
  if (!summary?.trim()) {
    return false;
  }
  return /OVERALL:\s*FAIL/i.test(summary);
}

/** Most recent finished review with OVERALL: FAIL, if any. */
export function findLatestFailedReview(
  history: CycleRecord[],
): CycleRecord | undefined {
  for (let index = history.length - 1; index >= 0; index--) {
    const record = history[index];
    if (record.phase !== "review" || record.status !== "finished") {
      continue;
    }
    return isReviewFail(record.summary) ? record : undefined;
  }
  return undefined;
}

export function formatFailedReviewForDevelop(record: CycleRecord): string {
  const body = record.summary?.trim() ?? "(review produced no summary text)";
  return [
    "## Review feedback (FAIL — fix before next review)",
    "",
    `The reviewer rejected the last implementation (run \`${record.runId}\`, cycle ${record.cycle}).`,
    "Address **every** blocking issue and criterion below until the work would earn **OVERALL: PASS**.",
    "Re-work the **same** task in **## Progress** — do not move on to a different roadmap ID.",
    "",
    body,
  ].join("\n");
}
