import { Agent } from "@cursor/sdk";
import { resolveConfig } from "./config.js";
import { logRunErrorDetails } from "./run-diagnostics.js";
import { loadState } from "./state.js";

export async function inspectLastRun(
  configPath: string | undefined,
  runIdArg?: string,
): Promise<void> {
  const config = await resolveConfig({ configPath, requireSpec: false });
  const state = await loadState(config.projectRoot);
  const runId = runIdArg ?? state.lastRunId;

  if (!runId) {
    console.error("[curious] no run id (pass one or run a phase first)");
    process.exit(1);
  }

  if (!state.agentId) {
    console.error("[curious] no agent id in state");
    process.exit(1);
  }

  const apiKey = config.apiKey ?? process.env.CURSOR_API_KEY;
  if (!apiKey) {
    console.error("[curious] CURSOR_API_KEY required");
    process.exit(1);
  }

  const run = await Agent.getRun(runId, {
    runtime: config.runtime === "cloud" ? "cloud" : "local",
    cwd: config.cwd,
    agentId: state.agentId,
    apiKey,
  });

  console.log(`[curious] inspect ${runId} status=${run.status}`);
  await logRunErrorDetails(run);
}
