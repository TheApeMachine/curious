import { readFile } from "node:fs/promises";
import path from "node:path";
import { CURIOUS_MODEL } from "./model.js";
import {
  CONFIG_FILENAME,
  DEFAULT_SPEC_REL,
  discoverProjectInParents,
  resolveProjectAtDirectory,
  shouldDiscoverParents,
  slugFromPath,
} from "./project.js";
import { hostArchLabel, isArm64Host } from "./workflow-policy.js";
import type { CuriousConfig, RuntimeKind } from "./types.js";

function defaultConfig(projectRoot: string, specPath: string): CuriousConfig {
  return {
    specPath,
    cwd: projectRoot,
    runtime: "local",
    model: CURIOUS_MODEL,
    cycleDelayMs: 0,
    maxCycles: 0,
    overseerEveryNCycles: 5,
    overseerOnReviewFailStreak: 2,
    settingSources: ["project"],
    agentName: `curious-${slugFromPath(projectRoot)}`,
    agentId: `agent-curious-${slugFromPath(projectRoot)}`,
  };
}

function mergeConfig(
  base: CuriousConfig,
  override: Partial<CuriousConfig>,
  resolveRelativeTo: string,
): CuriousConfig {
  const cwd = override.cwd
    ? path.isAbsolute(override.cwd)
      ? override.cwd
      : path.resolve(resolveRelativeTo, override.cwd)
    : base.cwd;

  const specPath = override.specPath
    ? path.isAbsolute(override.specPath)
      ? override.specPath
      : path.resolve(resolveRelativeTo, override.specPath)
    : base.specPath;

  const { model: _modelIgnored, ...rest } = override;

  return {
    ...base,
    ...rest,
    cwd,
    specPath,
    model: CURIOUS_MODEL,
    cloud: override.cloud ?? base.cloud,
  };
}

export function configFromEnv(): Partial<CuriousConfig> {
  const partial: Partial<CuriousConfig> = {};
  if (process.env.CURIOUS_SPEC_PATH) partial.specPath = process.env.CURIOUS_SPEC_PATH;
  if (process.env.CURIOUS_CWD) partial.cwd = process.env.CURIOUS_CWD;
  if (process.env.CURIOUS_RUNTIME) {
    partial.runtime = process.env.CURIOUS_RUNTIME as RuntimeKind;
  }
  if (process.env.CURIOUS_AGENT_ID) partial.agentId = process.env.CURIOUS_AGENT_ID;
  if (process.env.CURIOUS_CYCLE_DELAY_MS) {
    partial.cycleDelayMs = Number(process.env.CURIOUS_CYCLE_DELAY_MS);
  }
  if (process.env.CURIOUS_MAX_CYCLES) {
    partial.maxCycles = Number(process.env.CURIOUS_MAX_CYCLES);
  }
  if (process.env.CURIOUS_OVERSEER_EVERY_N_CYCLES) {
    partial.overseerEveryNCycles = Number(process.env.CURIOUS_OVERSEER_EVERY_N_CYCLES);
  }
  if (process.env.CURIOUS_OVERSEER_FAIL_STREAK) {
    partial.overseerOnReviewFailStreak = Number(
      process.env.CURIOUS_OVERSEER_FAIL_STREAK,
    );
  }
  if (process.env.CURIOUS_AGENT_BRANCH) {
    partial.agentBranch = process.env.CURIOUS_AGENT_BRANCH;
  }
  if (process.env.CURIOUS_ENSURE_AGENT_BRANCH !== undefined) {
    partial.ensureAgentBranch = ["1", "true", "yes"].includes(
      process.env.CURIOUS_ENSURE_AGENT_BRANCH.toLowerCase(),
    );
  }
  return partial;
}

async function loadConfigFile(filePath: string): Promise<Partial<CuriousConfig>> {
  const raw = await readFile(filePath, "utf8");
  return JSON.parse(raw) as Partial<CuriousConfig>;
}

export interface ResolvedConfig extends CuriousConfig {
  projectRoot: string;
  hasSpec: boolean;
}

export interface ResolveOptions {
  configPath?: string;
  /** If false, bootstrap can run without spec/SPEC.md yet */
  requireSpec?: boolean;
}

async function locateProject(options: ResolveOptions): Promise<{
  projectRoot: string;
  specPath: string;
  hasSpec: boolean;
  configPath?: string;
}> {
  const { configPath } = options;

  if (configPath) {
    const projectRoot = path.dirname(path.resolve(configPath));
    const discovered = await resolveProjectAtDirectory(projectRoot);
    return { ...discovered, configPath: path.resolve(configPath) };
  }

  const startDir = process.env.CURIOUS_CWD ?? process.cwd();

  if (shouldDiscoverParents()) {
    const fromParents = await discoverProjectInParents(startDir);
    if (fromParents) {
      return fromParents;
    }
  }

  return resolveProjectAtDirectory(startDir);
}

export async function resolveConfig(
  options: ResolveOptions = {},
): Promise<ResolvedConfig> {
  const { requireSpec = true } = options;
  const located = await locateProject(options);

  if (requireSpec && !located.hasSpec) {
    throw new Error(
      `No ${DEFAULT_SPEC_REL} in ${located.projectRoot}.\n` +
        `Run commands from your project root, or: curious bootstrap`,
    );
  }

  let fileOverrides: Partial<CuriousConfig> = {};

  if (located.configPath) {
    fileOverrides = await loadConfigFile(located.configPath);
  }

  const base = defaultConfig(located.projectRoot, located.specPath);
  const merged = mergeConfig(base, fileOverrides, located.projectRoot);
  const withEnv = mergeConfig(merged, configFromEnv(), located.projectRoot);

  return {
    ...withEnv,
    projectRoot: located.projectRoot,
    hasSpec: located.hasSpec,
  };
}

export function printConfigSummary(config: ResolvedConfig): void {
  console.log(`[curious] project root: ${config.projectRoot}`);
  console.log(`[curious] spec: ${config.specPath}${config.hasSpec ? "" : " (will be created)"}`);
  console.log(`[curious] agent cwd: ${config.cwd}`);
  console.log(`[curious] model: ${config.model.id} (fixed)`);
  console.log(
    `[curious] host: ${hostArchLabel()} (verify on this arch only${isArm64Host() ? "; amd64-tagged tests N/A" : ""})`,
  );
  console.log("[curious] commits: human only (agents must not git commit)");
  if (config.ensureAgentBranch !== false) {
    const { currentBranch, gitToplevel } = await import("./git-branch.js");
    const root = await gitToplevel(config.projectRoot);
    const branch = root ? await currentBranch(root) : null;
    const target = config.agentBranch ?? "curious";
    const pending = root && branch !== target;
    console.log(
      `[curious] git branch: ${branch ?? target}` +
        (pending ? " (will switch before agent runs)" : ""),
    );
  }
  if (config.overseerEveryNCycles > 0 || config.overseerOnReviewFailStreak > 0) {
    const parts: string[] = [];
    if (config.overseerEveryNCycles > 0) {
      parts.push(`every ${config.overseerEveryNCycles} task cycle(s)`);
    }
    if (config.overseerOnReviewFailStreak > 0) {
      parts.push(`after ${config.overseerOnReviewFailStreak} review FAIL(s)`);
    }
    console.log(`[curious] overseer: ${parts.join("; ")}`);
  } else {
    console.log("[curious] overseer: disabled");
  }
}
