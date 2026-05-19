import { spawnSync } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { loadAgentsDocument } from "./project.js";
import { analyzeRoadmap } from "./spec-roadmap.js";
import { extractSpecSection } from "./spec-sections.js";
import type { CycleRecord, Phase } from "./types.js";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cliEntry = path.join(repoRoot, "dist/index.js");
const specPath = path.join(repoRoot, "spec/SPEC.md");
const statePath = path.join(repoRoot, ".curious/state.json");

function runCli(args: string[]): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync(process.execPath, [cliEntry, ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    env: process.env,
  });
  return {
    status: result.status,
    stdout: result.stdout,
    stderr: result.stderr,
  };
}

function completedDevelopReviewSync(
  history: CycleRecord[],
  minCycle = 3,
): boolean {
  const phasesByCycle = new Map<number, Set<Phase>>();

  for (const record of history) {
    if (record.status !== "finished") {
      continue;
    }
    const phases = phasesByCycle.get(record.cycle) ?? new Set<Phase>();
    phases.add(record.phase);
    phasesByCycle.set(record.cycle, phases);
  }

  for (const [cycle, phases] of phasesByCycle) {
    if (
      cycle >= minCycle &&
      phases.has("develop") &&
      phases.has("review") &&
      phases.has("sync")
    ) {
      return true;
    }
  }

  return false;
}

describe("npm test wiring", () => {
  it("runs node:test on compiled dist output", () => {
    assert.equal(typeof describe, "function");
  });
});

describe("dogfood smoke — build artifacts", () => {
  it("loads AGENTS.md from the repository root", async () => {
    const agents = await loadAgentsDocument(repoRoot, repoRoot);
    assert.ok(agents);
    assert.equal(agents.relPath, "AGENTS.md");
    assert.match(agents.content, /node:test/);
  });

  it("parses spec/SPEC.md roadmap with unchecked tasks", async () => {
    const specBody = await readFile(specPath, "utf8");
    const roadmap = analyzeRoadmap(specBody);
    assert.ok(roadmap.totalTasks > 0);
    assert.ok(roadmap.uncheckedTaskIds.length > 0);
    assert.match(roadmap.uncheckedTaskIds[0]!, /^T\d+\.\d+$/);
  });

  it("finds an unchecked task in ## Progress", async () => {
    const specBody = await readFile(specPath, "utf8");
    const progress = extractSpecSection(specBody, "## Progress");
    assert.ok(progress);
    assert.match(progress, /- \[ \] T\d+\.\d+ —/);
  });
});

describe("dogfood smoke — CLI", () => {
  it("prints help via the help subcommand", () => {
    const { status, stdout } = runCli(["help"]);
    assert.equal(status, 0);
    assert.match(stdout, /curious — spec-driven agent workflow/);
    assert.match(stdout, /curious run --cycle/);
  });

  it("status exits zero and returns persisted orchestrator state", async () => {
    await access(statePath);
    const { status, stdout } = runCli(["status"]);
    assert.equal(status, 0);

    const payload = JSON.parse(stdout) as {
      config: { projectRoot: string; specPath: string };
      state: { phase: string; cycle: number; history: CycleRecord[] };
    };

    assert.equal(payload.config.projectRoot, repoRoot);
    assert.ok(payload.config.specPath.endsWith("spec/SPEC.md"));
    assert.ok(["develop", "review", "sync", "overseer"].includes(payload.state.phase));
    assert.ok(Array.isArray(payload.state.history));
    assert.ok(payload.state.history.length > 0);
  });
});

describe("dogfood smoke — orchestrator history", () => {
  it("records a finished develop→review→sync cycle on this host", async () => {
    const raw = await readFile(statePath, "utf8");
    const state = JSON.parse(raw) as { history: CycleRecord[] };
    assert.equal(
      completedDevelopReviewSync(state.history),
      true,
      "expected at least one finished develop/review/sync cycle (cycle >= 3)",
    );
  });
});
