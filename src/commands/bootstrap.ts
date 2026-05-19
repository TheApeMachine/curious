import { mkdir } from "node:fs/promises";
import path from "node:path";
import { resolveConfig } from "../config.js";
import { runAgentTask } from "../agent-run.js";
import { buildBootstrapPrompt } from "../prompts-tasks.js";
import { DEFAULT_SPEC_REL } from "../project.js";

export async function runBootstrap(
  configPath: string | undefined,
  verbose: boolean,
): Promise<void> {
  const config = await resolveConfig({ configPath, requireSpec: false });

  if (config.hasSpec) {
    console.log(
      `[curious] ${DEFAULT_SPEC_REL} already exists — bootstrap will overwrite/refine it`,
    );
  } else {
    await mkdir(path.dirname(config.specPath), { recursive: true });
    console.log(`[curious] will create ${DEFAULT_SPEC_REL}`);
  }

  const prompt = await buildBootstrapPrompt(config);
  const result = await runAgentTask(config, prompt, {
    verbose,
    label: "bootstrap",
  });

  if (result.status !== "finished") {
    process.exit(1);
  }

  console.log("\n[curious] Next steps:");
  console.log("  1. Review and refine spec/SPEC.md");
  console.log("  2. curious roadmap     # expand tasks if needed");
  console.log("  3. curious run --cycle # developer → reviewer → sync");
}
