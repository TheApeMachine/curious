import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { ResolvedConfig } from "../config.js";
import { loadState, statePath } from "../state.js";
import { harvestDpoPairs, type DpoExample } from "./dpo.js";

export type HarvestFormat = "dpo";

export interface HarvestOptions {
  format: HarvestFormat;
  outputPath?: string;
  minQuality: number;
  includeRejected: boolean;
}

export interface HarvestResult {
  format: HarvestFormat;
  outputPath: string;
  exampleCount: number;
  skippedLowQuality: number;
}

function defaultOutputPath(projectRoot: string, format: HarvestFormat): string {
  return path.join(projectRoot, ".curious", "harvest", `${format}.jsonl`);
}

function resolveHarvestOutput(
  projectRoot: string,
  format: HarvestFormat,
  configured?: string,
): string {
  if (!configured) {
    return defaultOutputPath(projectRoot, format);
  }
  const resolved = path.isAbsolute(configured)
    ? configured
    : path.join(projectRoot, configured);
  if (resolved.endsWith("/") || resolved.endsWith(path.sep)) {
    return path.join(resolved, `${format}.jsonl`);
  }
  const ext = path.extname(resolved);
  if (!ext || ext === ".jsonl") {
    return ext ? resolved : path.join(resolved, `${format}.jsonl`);
  }
  return resolved;
}

export async function runHarvest(
  config: ResolvedConfig,
  options: HarvestOptions,
): Promise<HarvestResult> {
  const state = await loadState(config.projectRoot);
  const outputPath = resolveHarvestOutput(
    config.projectRoot,
    options.format,
    options.outputPath ?? config.harvest?.output,
  );

  if (options.format !== "dpo") {
    throw new Error(`Unsupported harvest format: ${options.format}`);
  }

  const allExamples = await harvestDpoPairs(state, {
    projectRoot: config.projectRoot,
    cwd: config.cwd,
    specPath: config.specPath,
    minQuality: options.minQuality,
    includeRejected: options.includeRejected,
  });

  const accepted = allExamples.filter(
    (example) => example.quality_score >= options.minQuality,
  );
  const skippedLowQuality = allExamples.length - accepted.length;

  await mkdir(path.dirname(outputPath), { recursive: true });
  const body =
    accepted.map((example) => JSON.stringify(example)).join("\n") +
    (accepted.length > 0 ? "\n" : "");
  await writeFile(outputPath, body, "utf8");

  return {
    format: options.format,
    outputPath,
    exampleCount: accepted.length,
    skippedLowQuality,
  };
}

export type { DpoExample };
