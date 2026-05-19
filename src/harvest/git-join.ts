import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export async function isGitRepository(cwd: string): Promise<boolean> {
  try {
    await execFileAsync("git", ["rev-parse", "--git-dir"], { cwd, timeout: 10_000 });
    return true;
  } catch {
    return false;
  }
}

/** Nearest commit on HEAD at or before `isoTime` (exclusive of future commits). */
export async function gitCommitBefore(
  cwd: string,
  isoTime: string,
): Promise<string | null> {
  try {
    const { stdout } = await execFileAsync(
      "git",
      ["rev-list", "-1", `--before=${isoTime}`, "HEAD"],
      { cwd, timeout: 30_000 },
    );
    const sha = stdout.trim();
    return sha.length > 0 ? sha : null;
  } catch {
    return null;
  }
}

export async function gitDiffBetween(
  cwd: string,
  fromSha: string,
  toSha: string,
): Promise<string | null> {
  if (fromSha === toSha) {
    return "";
  }
  try {
    const { stdout } = await execFileAsync(
      "git",
      ["diff", `${fromSha}..${toSha}`],
      { cwd, timeout: 120_000, maxBuffer: 16 * 1024 * 1024 },
    );
    return stdout;
  } catch {
    return null;
  }
}

export async function gitShowStat(
  cwd: string,
  sha: string,
): Promise<string | null> {
  try {
    const { stdout } = await execFileAsync(
      "git",
      ["show", "--stat", "--format=", sha],
      { cwd, timeout: 60_000, maxBuffer: 4 * 1024 * 1024 },
    );
    return stdout.trim() || null;
  } catch {
    return null;
  }
}
