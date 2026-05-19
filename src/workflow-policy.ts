import os from "node:os";

/** Node `process.arch` for the machine running curious (e.g. arm64, x64). */
export function hostArchLabel(): string {
  return os.arch();
}

export function isArm64Host(): boolean {
  return hostArchLabel() === "arm64";
}

/** Lines that conflict with human-commit / host-only workflow — dropped from injected steering. */
const FORBIDDEN_STEERING_LINE =
  /\b(git add|git commit|commit first|must commit|you must commit|leave changes staged for human)\b|\bworktree\b|github actions?\b|\bCI artifact\b|paste amd64|amd64\+avx512|branch[- ]tip.*\bHEAD\b|uncommitted.*\bHEAD\b|pasted amd64/i;

export function sanitizeSteering(text: string): {
  text: string;
  strippedCount: number;
} {
  const lines = text.split("\n");
  const kept: string[] = [];
  let strippedCount = 0;

  for (const line of lines) {
    const body = line.replace(/^[-*]\s*/, "").trim();
    if (body.length > 0 && FORBIDDEN_STEERING_LINE.test(body)) {
      strippedCount += 1;
      continue;
    }
    kept.push(line);
  }

  const joined = kept.join("\n").trim();
  if (strippedCount > 0 && joined.length === 0) {
    return { text: "", strippedCount };
  }

  if (strippedCount > 0) {
    return {
      text: [
        joined,
        "",
        `_(Curious omitted ${strippedCount} steering line(s) that required commits, CI, worktrees, or amd64-on-arm proof.)_`,
      ].join("\n"),
      strippedCount,
    };
  }

  return { text: joined, strippedCount: 0 };
}

/** When agents are unsure, they must verify by reading files — not memory or summaries. */
export const SOURCE_OF_TRUTH_SECTION = `### When in doubt — read the files

**Source of truth is on-disk content**, not prior chat, orchestrator history, review summaries, \`git log\` messages, or assumptions about \`HEAD\`.

- Unclear whether work landed, what changed, or if the spec/AGENTS.md allows something → **read** the paths (\`read\`, \`grep\`, \`git diff\`, \`git status\`) and cite **file:line** evidence.
- Conflicts between a summary and the tree → **trust the files**.
- Do not FAIL or block on claims you have not verified in the working tree.`;

export function buildWorkflowPolicySection(hostArch: string): string {
  const hostNote =
    hostArch === "arm64"
      ? `\n**This run is on arm64.** Tests behind \`//go:build amd64\` (or OS=linux GOARCH=amd64 cross-build) are **not** required to execute here. Verify implementation via host-runnable tests, file inspection, and \`git diff\` — not by pasting amd64 bench output.`
      : hostArch === "x64" || hostArch === "amd64"
        ? `\n**This run is on ${hostArch}.** Run amd64-tagged tests when present; still do not require CI or agent commits.`
        : `\n**Host architecture:** \`${hostArch}\`. Run only tests that execute on this machine; do not require CI for verification.`;

  return `## Workflow (binding — human + host)

**Curious host:** \`${hostArch}\`${hostNote}

### Commits (human only)

- The **human** commits, pushes, and manages branches — **not** agents.
- Judge deliverables from the **working tree** (\`git diff\`, \`git status\`, file reads). **Uncommitted** fixes are valid and expected.
- **Do not** FAIL review because changes are not committed or not on \`HEAD\`.
- **Do not** tell the developer to \`git add\`, \`git commit\`, use **worktrees**, or wait for a commit before continuing.
- Agents use **read-only** git only (see Git policy).

### Verification (this machine only)

- Develop and review run tests **on this host** — no GitHub Actions, no CI URLs, no cross-arch test runs unless they actually execute here.
- **5_verification: PASS** when host-runnable tests pass (or were run and documented) and the implementation is present in the working tree.
- **5_verification: FAIL** only for wrong/missing code, failing host tests, or absent required tests that **can** run on this host — **not** for missing amd64-only output on arm64.
- Cross-arch / SIMD code: confirm sources, build tags, and dispatch wiring; run packages that compile and test on the host; note amd64-only proof as **optional human follow-up**, not a loop blocker.

${SOURCE_OF_TRUTH_SECTION}`;
}

/** Appended to develop prompt when re-working after a failed review. */
export const REVIEW_FAIL_WORKFLOW_NOTE = `**Workflow override:** Ignore prior blocking issues that only demand **git commit**, **branch-tip == HEAD**, **GitHub Actions / CI artifacts**, **worktrees**, or **amd64 test output on an arm64 host**. Satisfy code and host-runnable test requirements in the working tree instead. If a prior claim is unclear, **read the files** — on-disk content is the source of truth.`;

/** Suggested bullets for spec ## Constraints at bootstrap. */
export const WORKFLOW_SPEC_CONSTRAINTS = [
  "Human commits only; agents must not run mutating git commands.",
  "Agents verify on the local host architecture only (no CI required for review PASS).",
  "On arm64, amd64-tagged tests are optional for agent review; host-runnable tests and code inspection suffice.",
  "When uncertain, read source files and git diff — file content is the source of truth.",
].join(" ");
