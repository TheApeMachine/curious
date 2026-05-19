import type { CuriousConfig, CuriousState, CycleRecord } from "./types.js";

const HISTORY_LIMIT = 40;

/** Run overseer after sync when interval matches or review failures repeat. */
export function shouldRunOverseer(
  state: CuriousState,
  config: CuriousConfig,
): boolean {
  const interval = config.overseerEveryNCycles;
  const failStreak = config.overseerOnReviewFailStreak;

  if (interval <= 0 && failStreak <= 0) {
    return false;
  }

  if (
    interval > 0 &&
    state.cycle > 0 &&
    state.cycle % interval === 0
  ) {
    return true;
  }

  if (failStreak > 0 && countTrailingReviewFails(state.history) >= failStreak) {
    return true;
  }

  return false;
}

export function overseerTriggerReason(
  state: CuriousState,
  config: CuriousConfig,
): string {
  const interval = config.overseerEveryNCycles;
  const failStreak = config.overseerOnReviewFailStreak;
  const trailingFails = countTrailingReviewFails(state.history);

  if (
    interval > 0 &&
    state.cycle > 0 &&
    state.cycle % interval === 0
  ) {
    return `completed ${state.cycle} task cycle(s) (every ${interval})`;
  }

  if (failStreak > 0 && trailingFails >= failStreak) {
    return `${trailingFails} consecutive review FAIL(s)`;
  }

  return "scheduled";
}

export function countTrailingReviewFails(history: CycleRecord[]): number {
  let count = 0;

  for (let index = history.length - 1; index >= 0; index--) {
    const record = history[index];
    if (record.phase !== "review" || record.status !== "finished") {
      break;
    }
    if (!reviewSummaryIsFail(record.summary)) {
      break;
    }
    count++;
  }

  return count;
}

function reviewSummaryIsFail(summary?: string): boolean {
  if (!summary) return false;
  return /OVERALL:\s*FAIL/i.test(summary);
}

/** Recent orchestrator history for the overseer prompt. */
export function formatHistoryForOverseer(history: CycleRecord[]): string {
  const recent = history.slice(-HISTORY_LIMIT);
  if (recent.length === 0) {
    return "(no prior runs recorded)";
  }

  const lines = [
    "| Cycle | Phase | Status | Summary |",
    "| ----- | ----- | ------ | ------- |",
  ];

  for (const record of recent) {
    const summary = (record.summary ?? "—")
      .replace(/\|/g, "\\|")
      .replace(/\n/g, " ")
      .slice(0, 200);
    lines.push(
      `| ${record.cycle} | ${record.phase} | ${record.status} | ${summary} |`,
    );
  }

  return lines.join("\n");
}
