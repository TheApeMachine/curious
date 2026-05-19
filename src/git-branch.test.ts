import { execFile } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { describe, it } from "node:test";
import {
  currentBranch,
  ensureAgentBranch,
  gitToplevel,
} from "./git-branch.js";

const execFileAsync = promisify(execFile);

async function git(cwd: string, ...args: string[]): Promise<void> {
  await execFileAsync("git", args, { cwd });
}

describe("ensureAgentBranch", () => {
  it("creates and switches to curious", async () => {
    const repoDir = await mkdtemp(path.join(os.tmpdir(), "curious-git-"));
    await git(repoDir, "init");
    await git(repoDir, "config", "user.email", "test@example.com");
    await git(repoDir, "config", "user.name", "Test");
    await writeFile(path.join(repoDir, "README.md"), "hi\n", "utf8");
    await git(repoDir, "add", "README.md");
    await git(repoDir, "commit", "-m", "init");

    const before = await currentBranch(repoDir);
    assert.ok(before === "main" || before === "master");
    const branch = await ensureAgentBranch(repoDir, "curious");
    assert.equal(branch, "curious");
    assert.equal(await currentBranch(repoDir), "curious");
  });

  it("is idempotent when already on curious", async () => {
    const repoDir = await mkdtemp(path.join(os.tmpdir(), "curious-git-"));
    await git(repoDir, "init");
    await git(repoDir, "config", "user.email", "test@example.com");
    await git(repoDir, "config", "user.name", "Test");
    await writeFile(path.join(repoDir, "README.md"), "hi\n", "utf8");
    await git(repoDir, "add", "README.md");
    await git(repoDir, "commit", "-m", "init");

    await ensureAgentBranch(repoDir, "curious");
    await ensureAgentBranch(repoDir, "curious");
    assert.equal(await currentBranch(repoDir), "curious");
  });

  it("switches back from another branch", async () => {
    const repoDir = await mkdtemp(path.join(os.tmpdir(), "curious-git-"));
    await git(repoDir, "init");
    await git(repoDir, "config", "user.email", "test@example.com");
    await git(repoDir, "config", "user.name", "Test");
    await writeFile(path.join(repoDir, "README.md"), "hi\n", "utf8");
    await git(repoDir, "add", "README.md");
    await git(repoDir, "commit", "-m", "init");

    await ensureAgentBranch(repoDir, "curious");
    await git(repoDir, "switch", "-c", "feature-x");
    assert.equal(await currentBranch(repoDir), "feature-x");
    await ensureAgentBranch(repoDir, "curious");
    assert.equal(await currentBranch(repoDir), "curious");
  });

  it("skips when disabled", async () => {
    const repoDir = await mkdtemp(path.join(os.tmpdir(), "curious-git-"));
    await git(repoDir, "init");
    await git(repoDir, "config", "user.email", "test@example.com");
    await git(repoDir, "config", "user.name", "Test");
    await writeFile(path.join(repoDir, "README.md"), "hi\n", "utf8");
    await git(repoDir, "add", "README.md");
    await git(repoDir, "commit", "-m", "init");

    const before = await currentBranch(repoDir);
    const result = await ensureAgentBranch(repoDir, "curious", false);
    assert.equal(result, null);
    assert.equal(await currentBranch(repoDir), before);
  });

  it("returns null for non-git directory", async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), "curious-nogit-"));
    assert.equal(await gitToplevel(dir), null);
    assert.equal(await ensureAgentBranch(dir, "curious"), null);
  });
});
