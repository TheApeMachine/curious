export type VerdictOverall = "PASS" | "FAIL";

export interface ReviewVerdict {
  overall: VerdictOverall;
  criteria: Record<string, "PASS" | "FAIL">;
  blockingIssues: string[];
  evidence: string[];
  nextDevelop?: string;
}

const VERDICT_FENCE = /```review-verdict\s*([\s\S]*?)```/i;

/** Parse a structured `review-verdict` block from a review summary. */
export function parseReviewVerdict(summary?: string): ReviewVerdict | null {
  if (!summary?.trim()) {
    return null;
  }

  const match = summary.match(VERDICT_FENCE);
  const body = match?.[1] ?? tryUnfencedVerdict(summary);
  if (!body) {
    return null;
  }

  const overallMatch = body.match(/OVERALL:\s*(PASS|FAIL)/i);
  if (!overallMatch) {
    return null;
  }

  const overall = overallMatch[1].toUpperCase() as VerdictOverall;
  const criteria: Record<string, "PASS" | "FAIL"> = {};

  for (const line of body.split("\n")) {
    const criterion = line.match(/^(\d+_[\w]+):\s*(PASS|FAIL)/i);
    if (criterion) {
      criteria[criterion[1]] = criterion[2].toUpperCase() as "PASS" | "FAIL";
    }
  }

  return {
    overall,
    criteria,
    blockingIssues: parseListSection(body, "blocking_issues"),
    evidence: parseListSection(body, "evidence"),
    nextDevelop: parseScalarSection(body, "next_develop"),
  };
}

function tryUnfencedVerdict(summary: string): string | null {
  if (!/OVERALL:\s*(PASS|FAIL)/i.test(summary)) {
    return null;
  }
  return summary;
}

function isSectionHeader(line: string): boolean {
  return /^\s*[\w][\w_]*:\s*(\S.*)?$/.test(line) && !/^\s*[-*]/.test(line);
}

function parseListSection(body: string, key: string): string[] {
  const lines = body.split("\n");
  const headerIndex = lines.findIndex((line) =>
    new RegExp(`^\\s*${key}:\\s*$`, "i").test(line),
  );
  if (headerIndex === -1) {
    return [];
  }

  const items: string[] = [];
  for (let index = headerIndex + 1; index < lines.length; index++) {
    const line = lines[index];
    if (isSectionHeader(line)) {
      break;
    }
    const item = line.replace(/^\s*[-*]\s*/, "").trim();
    if (item.length > 0 && item !== "-" && !/^none$/i.test(item)) {
      items.push(item);
    }
  }
  return items;
}

function parseScalarSection(body: string, key: string): string | undefined {
  const lines = body.split("\n");
  const headerIndex = lines.findIndex((line) =>
    new RegExp(`^\\s*${key}:\\s*$`, "i").test(line),
  );
  if (headerIndex === -1) {
    return undefined;
  }

  for (let index = headerIndex + 1; index < lines.length; index++) {
    const line = lines[index].trim();
    if (!line) {
      continue;
    }
    if (isSectionHeader(lines[index])) {
      break;
    }
    const value = line.replace(/^[-*]\s*/, "").trim();
    if (value && value !== "-" && !/^none$/i.test(value)) {
      return value;
    }
  }
  return undefined;
}

/** Extract roadmap task id (T1.2, M0) from free text. */
export function extractTaskId(text?: string): string | undefined {
  if (!text?.trim()) {
    return undefined;
  }
  const match = text.match(/\b(T\d+\.\d+|M\d+)\b/);
  return match?.[1];
}
