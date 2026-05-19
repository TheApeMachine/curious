import { Agent } from "@cursor/sdk";
import { resolveConfig } from "./config.js";
import {
  formatFailureModeHint,
  formatInspectHeader,
  logRunErrorDetails,
} from "./run-diagnostics.js";
import { loadState } from "./state.js";

export async function inspectLastRun(
  configPath: string | undefined,
  runIdArg?: string,
): Promise<void> {
  const config = await resolveConfig({ configPath, requireSpec: false });
  const state = await loadState(config.projectRoot);
  const runId = runIdArg ?? state.lastRunId;

  if (!runId) {
    const hint = formatFailureModeHint("no run id");
    console.error("[curious] no run id (pass one or run a phase first)");
    if (hint) {
      console.error(`[curious] hint: ${hint}`);
    }
    process.exit(1);
  }

  if (!state.agentId) {
    console.error("[curious] no agent id in state");
    process.exit(1);
  }

  const apiKey = config.apiKey ?? process.env.CURSOR_API_KEY;
  if (!apiKey) {
    const hint = formatFailureModeHint("CURSOR_API_KEY required");
    console.error("[curious] CURSOR_API_KEY required");
    if (hint) {
      console.error(`[curious] hint: ${hint}`);
    }
    process.exit(1);
  }

  const run = await Agent.getRun(runId, {
    runtime: config.runtime === "cloud" ? "cloud" : "local",
    cwd: config.cwd,
    agentId: state.agentId,
    apiKey,
  });

  console.log(
    formatInspectHeader(runId, run.status, {
      phase: state.phase,
      cycle: state.cycle,
      lastError: state.lastError,
    }),
  );

  const hint = formatFailureModeHint(state.lastError);
  if (hint) {
    console.error(`[curious] hint: ${hint}`);
  }

  if (run.status === "error" || run.status === "cancelled") {
    await logRunErrorDetails(run);
    return;
  }

  if (run.result?.trim()) {
    console.log("--- run.result ---");
    console.log(run.result);
    return;
  }

  console.log("[curious] run finished without stored result text");
}
