import { Agent, CursorAgentError, type RunResult } from "@cursor/sdk";
import { buildAgentOptions } from "./agent.js";
import type { ResolvedConfig } from "./config.js";
import { logRunFailure } from "./run-diagnostics.js";
import { consumeRunStream } from "./stream.js";

export interface RunTaskOptions {
  verbose?: boolean;
  label?: string;
}

/**
 * One-shot agent task with streaming progress (does not use the dev-loop agent).
 */
export async function runAgentTask(
  config: ResolvedConfig,
  prompt: string,
  options: RunTaskOptions = {},
): Promise<RunResult> {
  const label = options.label ?? "task";
  console.log(`[curious] ${label} — starting agent`);

  const agentOptions = buildAgentOptions({
    ...config,
    agentName: `curious-${label}`,
    agentId: undefined,
  });

  const agent = await Agent.create(agentOptions);

  try {
    const run = await agent.send(prompt);
    console.log(`[curious] ${label} run ${run.id}`);
    console.log("[curious] agent working (tool progress below)…");

    const statusStop = run.onDidChangeStatus((status) => {
      console.log(`[curious] run status → ${status}`);
    });

    try {
      await consumeRunStream(run, { verbose: options.verbose, progress: true });
      const result = await run.wait();

      if (result.status === "error") {
        console.error(`[curious] ${label} failed`);
        await logRunFailure(run);
      } else if (result.status === "finished") {
        console.log(`[curious] ${label} finished in ${result.durationMs ?? "?"}ms`);
        if (result.result) {
          const preview =
            result.result.length > 500
              ? `${result.result.slice(0, 500)}…`
              : result.result;
          console.log(`[curious] ${preview}`);
        }
      }

      return result;
    } finally {
      statusStop();
    }
  } catch (err) {
    if (err instanceof CursorAgentError) {
      console.error(`[curious] ${label} startup failed: ${err.message}`);
    }
    throw err;
  } finally {
    await agent[Symbol.asyncDispose]();
  }
}
