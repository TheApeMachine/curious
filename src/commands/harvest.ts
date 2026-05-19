import path from "node:path";
import { resolveConfig } from "../config.js";
import { runHarvest, type HarvestFormat } from "../harvest/index.js";
import { statePath } from "../state.js";

function parseFormat(value: string): HarvestFormat {
  if (value === "dpo") {
    return value;
  }
  throw new Error(`Unknown harvest format: ${value} (supported: dpo)`);
}

export async function runHarvestCommand(
  configPath: string | undefined,
  argv: string[],
): Promise<void> {
  let format: HarvestFormat = "dpo";
  let outputPath: string | undefined;
  let minQuality = 0.5;
  let includeRejected = false;

  for (let index = 0; index < argv.length; index++) {
    const arg = argv[index];
    if (arg === "--format" || arg === "-f") {
      format = parseFormat(argv[++index] ?? "");
    } else if (arg === "--output" || arg === "-o") {
      outputPath = argv[++index];
    } else if (arg === "--min-quality") {
      minQuality = Number(argv[++index]);
      if (Number.isNaN(minQuality) || minQuality < 0 || minQuality > 1) {
        throw new Error("--min-quality must be a number between 0 and 1");
      }
    } else if (arg === "--include-rejected") {
      includeRejected = true;
    } else if (arg === "--help" || arg === "-h") {
      printHarvestHelp();
      return;
    }
  }

  const config = await resolveConfig({ configPath, requireSpec: false });

  if (config.harvest?.enabled === false) {
    console.log(
      "[curious] harvest: disabled in curious.config.json (set harvest.enabled true or remove the flag)",
    );
    console.log("[curious] harvest: proceeding anyway because CLI was invoked explicitly");
  }

  const stateFile = statePath(config.projectRoot);
  console.log(`[curious] harvest: reading ${stateFile}`);
  console.log(`[curious] harvest: format=${format} min_quality=${minQuality}`);

  const result = await runHarvest(config, {
    format,
    outputPath,
    minQuality,
    includeRejected,
  });

  console.log(
    `[curious] harvest: wrote ${result.exampleCount} example(s) → ${result.outputPath}`,
  );
  if (result.skippedLowQuality > 0) {
    console.log(
      `[curious] harvest: skipped ${result.skippedLowQuality} below min quality (use --include-rejected to emit)`,
    );
  }
}

function printHarvestHelp(): void {
  console.log(`curious harvest — export fine-tuning examples from .curious/state.json

Usage:
  curious harvest [--format dpo] [--output path] [--min-quality 0.5]

Options:
  --format, -f dpo          Export format (default: dpo)
  --output, -o path         Output JSONL file (default: .curious/harvest/dpo.jsonl)
  --min-quality N           Drop examples below this score 0–1 (default: 0.5)
  --include-rejected        Emit sub-threshold examples with reject_reason set

Reads orchestrator history only; does not run agents.
Joins git SHAs when the project root is a git repository.
Configure default output via curious.config.json:

  "harvest": { "enabled": true, "output": ".curious/harvest/" }
`);
}
