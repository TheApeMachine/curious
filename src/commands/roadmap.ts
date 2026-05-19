import { readFile } from "node:fs/promises";
import { resolveConfig } from "../config.js";
import { runAgentTask } from "../agent-run.js";
import { buildRoadmapPrompt } from "../prompts-tasks.js";

export async function runRoadmap(
  configPath: string | undefined,
  verbose: boolean,
): Promise<void> {
  const config = await resolveConfig({ configPath, requireSpec: true });
  const specBody = await readFile(config.specPath, "utf8");

  const prompt = await buildRoadmapPrompt(config, specBody);
  const result = await runAgentTask(config, prompt, {
    verbose,
    label: "roadmap",
  });

  if (result.status !== "finished") {
    process.exit(1);
  }

  console.log("\n[curious] Next steps:");
  console.log("  1. Review Roadmap and Progress in spec/SPEC.md");
  console.log("  2. curious run --cycle   # develop → review → sync");
}
