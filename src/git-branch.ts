import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const DEFAULT_AGENT_BRANCH = "curious";

async function runGit(
  cwd: string,
  args: string[],
): Promise<{ code: number; stdout: string; stderr: string }> {
  try {
    const { stdout, stderr } = await execFileAsync("git", args, { cwd });
    return { code: 0, stdout: stdout.trim(), stderr: stderr.trim() };
  } catch (err: unknown) {
    const e = err as { code?: number; stdout?: string; stderr?: string };
    return {
      code: e.code ?? 1,
      stdout: (e.stdout ?? "").toString().trim(),
      stderr: (e.stderr ?? "").toString().trim(),
    };
  }
}

export async function gitToplevel(start: string): Promise<string | null> {
  const result = await runGit(start, ["rev-parse", "--show-toplevel"]);
  if (result.code !== 0) return null;
  return result.stdout || null;
}

export async function currentBranch(repoRoot: string): Promise<string | null> {
  const result = await runGit(repoRoot, ["rev-parse", "--abbrev-ref", "HEAD"]);
  if (result.code !== 0) return null;
  return result.stdout || null;
}

async function branchExists(repoRoot: string, name: string): Promise<boolean> {
  const result = await runGit(repoRoot, [
    "show-ref",
    "--verify",
    "--quiet",
    `refs/heads/${name}`,
  ]);
  return result.code === 0;
}

export function agentBranchPromptNote(branch: string): string {
  return (
    `\n**Branch:** Curious switched this repo to \`${branch}\` before this run. ` +
    "Stay on this branch; do not run `git switch`, `git checkout`, or worktrees.\n"
  );
}

/**
 * Switch the repo to the Curious agent branch before agent work.
 * Returns the branch name, or null if skipped (not a git repo / disabled).
 */
export async function ensureAgentBranch(
  projectRoot: string,
  branch = DEFAULT_AGENT_BRANCH,
  enabled = true,
): Promise<string | null> {
  if (!enabled) return null;

  const root = await gitToplevel(projectRoot);
  if (!root) {
    console.log("[curious] git: not a repository — skipping agent branch switch");
    return null;
  }

  const current = await currentBranch(root);
  if (current === branch) {
    console.log(`[curious] git: already on branch ${branch}`);
    return branch;
  }

  let result: { code: number; stderr: string; stdout: string };
  if (await branchExists(root, branch)) {
    result = await runGit(root, ["switch", branch]);
    if (result.code !== 0) {
      result = await runGit(root, ["checkout", branch]);
    }
  } else {
    result = await runGit(root, ["switch", "-c", branch]);
    if (result.code !== 0) {
      result = await runGit(root, ["checkout", "-b", branch]);
    }
  }

  if (result.code !== 0) {
    const detail = result.stderr || result.stdout;
    throw new Error(
      `Failed to switch to branch ${JSON.stringify(branch)}` +
        (current ? ` (from ${current})` : "") +
        (detail ? `: ${detail}` : ""),
    );
  }

  console.log(
    `[curious] git: switched to branch ${branch}` +
      (current ? ` (from ${current})` : ""),
  );
  return branch;
}

export async function agentBranchPromptNoteForConfig(args: {
  projectRoot: string;
  agentBranch?: string;
  ensureAgentBranch?: boolean;
}): Promise<string> {
  if (args.ensureAgentBranch === false) return "";
  const root = await gitToplevel(args.projectRoot);
  if (!root) return "";
  const branch = (await currentBranch(root)) ?? args.agentBranch ?? DEFAULT_AGENT_BRANCH;
  return agentBranchPromptNote(branch);
}
