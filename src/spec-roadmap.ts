/** Task IDs used in ## Roadmap (T1.1, M0, …). */
const ROADMAP_TASK_LINE =
  /^\s*-\s+\[([ xX])\]\s+((?:T\d+\.\d+|M\d+)\b)/;

export interface RoadmapStatus {
  totalTasks: number;
  checkedTasks: number;
  uncheckedTaskIds: string[];
  /** True when the roadmap has at least one task and every task is checked. */
  complete: boolean;
}

function extractSection(body: string, heading: string): string | null {
  const start = body.match(new RegExp(`^${heading}\\s*$`, "m"));
  if (!start || start.index === undefined) return null;

  const after = body.slice(start.index + start[0].length);
  const next = after.match(/^## /m);
  const section = next?.index !== undefined ? after.slice(0, next.index) : after;
  return section;
}

/** Parse ## Roadmap checkboxes (T* / M* task IDs). */
export function analyzeRoadmap(specBody: string): RoadmapStatus {
  const section = extractSection(specBody, "## Roadmap");
  if (!section) {
    return {
      totalTasks: 0,
      checkedTasks: 0,
      uncheckedTaskIds: [],
      complete: false,
    };
  }

  const uncheckedTaskIds: string[] = [];
  let checkedTasks = 0;

  for (const line of section.split("\n")) {
    const match = line.match(ROADMAP_TASK_LINE);
    if (!match) continue;

    const id = match[2];
    const checked = match[1].toLowerCase() === "x";
    if (checked) {
      checkedTasks += 1;
    } else {
      uncheckedTaskIds.push(id);
    }
  }

  const totalTasks = checkedTasks + uncheckedTaskIds.length;

  return {
    totalTasks,
    checkedTasks,
    uncheckedTaskIds,
    complete: totalTasks > 0 && uncheckedTaskIds.length === 0,
  };
}
