import { readFile } from "node:fs/promises";
import { setTimeout as sleep } from "node:timers/promises";
import { CursorAgentError, type SDKAgent } from "@cursor/sdk";
import type { Run, SendOptions } from "@cursor/sdk";
import { connectAgent } from "./agent.js";
import { installConnectionGuard } from "./connection-guard.js";
import type { ResolvedConfig } from "./config.js";
import { printConfigSummary } from "./config.js";
import { loadAgentsDocument, relativeToRoot } from "./project.js";
import { buildPrompt } from "./prompts.js";
import {
  formatRunErrorSummary,
  logRunErrorDetails,
} from "./run-diagnostics.js";
import { consumeRunStream } from "./stream.js";
import {
  errorMessage,
  isAgentBusyError,
  isTransientError,
} from "./transient-errors.js";
import {
  overseerTriggerReason,
  shouldRunOverseer,
} from "./overseer.js";
import { findLatestFailedReview } from "./review-feedback.js";
import { agentSteeringForPhase } from "./spec-steering.js";
import { analyzeRoadmap } from "./spec-roadmap.js";
import { initialState, loadState, nextPhase, saveState } from "./state.js";
import type { CuriousConfig, CuriousState, CycleRecord, Phase } from "./types.js";

export interface OrchestratorOptions {
  verbose?: boolean;
  /** Run a single phase (develop, review, or sync) then exit. */
  once?: boolean;
  /**
   * Stop after this many full develop→review→sync rounds.
   * Omit for continuous mode (until Ctrl+C or config maxCycles).
   */
  cycles?: number;
  /** Stop when every ## Roadmap task checkbox is checked. */
  untilDone?: boolean;
}

const REMAINING_TASK_PREVIEW = 8;

function formatTaskIdList(ids: string[]): string {
  if (ids.length === 0) return "";
  if (ids.length <= REMAINING_TASK_PREVIEW) {
    return ids.join(", ");
  }
  const head = ids.slice(0, REMAINING_TASK_PREVIEW).join(", ");
  return `${head}, … (+${ids.length - REMAINING_TASK_PREVIEW} more)`;
}

export class Orchestrator {
  private agent?: SDKAgent;
  private stopping = false;
  private lastSummary?: string;
  /** True when we cancelled a run to recover from a dropped connection. */
  private recoveryCancel = false;

  constructor(
    private readonly config: ResolvedConfig,
    private readonly opts: OrchestratorOptions = {},
  ) {}

  requestStop(): void {
    this.stopping = true;
  }

  async run(): Promise<void> {
    printConfigSummary(this.config);

    let state = await loadState(this.config.projectRoot);
    state.running = true;
    await saveState(this.config.projectRoot, state);

    const shutdown = async () => {
      this.requestStop();
      if (state) {
        state.running = false;
        await saveState(this.config.projectRoot, state);
      }
    };

    process.once("SIGINT", shutdown);
    process.once("SIGTERM", shutdown);

    try {
      this.agent = await connectAgent(this.config, state.agentId);
      state.agentId = this.agent.agentId;
      await saveState(this.config.projectRoot, state);

      console.log(`[curious] agent ${this.agent.agentId} (${this.config.runtime})`);

      const cycleAtStart = state.cycle;
      const cyclesLimit = this.opts.cycles;
      let skipLoop = false;

      if (this.opts.once) {
        console.log("[curious] mode: single phase (--once)");
      } else if (this.opts.untilDone) {
        const initial = analyzeRoadmap(await readFile(this.config.specPath, "utf8"));
        this.logRoadmapStatus(initial);
        if (initial.complete) {
          console.log("[curious] roadmap already complete — nothing to do");
          skipLoop = true;
        } else {
          console.log(
            "[curious] mode: until done (stops when all ## Roadmap tasks are checked)",
          );
        }
      } else if (cyclesLimit !== undefined) {
        console.log(
          `[curious] mode: ${cyclesLimit} full cycle(s) (develop → review → sync), then stop`,
        );
      } else {
        console.log(
          "[curious] mode: continuous (Ctrl+C to stop; default is --until-done)",
        );
      }

      if (!skipLoop)
      do {
        state = await this.runPhase(state);
        if (this.stopping) break;

        if (this.opts.once) {
          this.printNextStepHint(state);
          break;
        }

        const completedCycles = state.cycle - cycleAtStart;
        const finishedRequestedCycles =
          cyclesLimit !== undefined &&
          state.phase === "develop" &&
          completedCycles >= cyclesLimit;

        if (finishedRequestedCycles) {
          console.log(
            `[curious] finished ${completedCycles} cycle(s) (developer → reviewer → sync)`,
          );
          this.printContinueHint(cyclesLimit);
          break;
        }

        if (this.opts.untilDone && (await this.roadmapJustCompleted(state))) {
          break;
        }

        if (cyclesLimit !== undefined && state.lastError) {
          console.log("[curious] cycle aborted due to phase error");
          break;
        }

        if (this.config.maxCycles > 0 && state.cycle >= this.config.maxCycles) {
          console.log(`[curious] reached maxCycles=${this.config.maxCycles}`);
          break;
        }

        if (state.phase === "develop" && state.cycle > cycleAtStart) {
          console.log(
            `[curious] next: cycle ${state.cycle} · develop (see spec Progress)`,
          );
          if (this.config.cycleDelayMs > 0) {
            console.log(`[curious] sleeping ${this.config.cycleDelayMs}ms`);
            await sleep(this.config.cycleDelayMs);
          }
        }
      } while (!this.stopping);
    } finally {
      process.removeListener("SIGINT", shutdown);
      process.removeListener("SIGTERM", shutdown);
      state = await loadState(this.config.projectRoot);
      state.running = false;
      await saveState(this.config.projectRoot, state);
      if (this.agent) {
        await this.agent[Symbol.asyncDispose]();
      }
    }
  }

  private async runPhase(state: CuriousState): Promise<CuriousState> {
    const phase = state.phase;
    const specBody = await readFile(this.config.specPath, "utf8");
    const agents = await loadAgentsDocument(
      this.config.projectRoot,
      this.config.cwd,
    );

    if (phase === "develop" && !agents) {
      console.warn(
        "[curious] warning: no AGENTS.md at project root or agent cwd — developer will lack style guidelines",
      );
    } else if (
      agents &&
      (phase === "develop" || phase === "review" || phase === "overseer")
    ) {
      console.log(`[curious] including AGENTS.md (${agents.relPath}) in prompt`);
    }

    if (phase === "overseer") {
      console.log(
        `[curious] overseer triggered: ${overseerTriggerReason(state, this.config)}`,
      );
    } else if (phase === "develop" && findLatestFailedReview(state.history)) {
      console.log(
        "[curious] injecting full failed review into develop prompt",
      );
    } else if (agentSteeringForPhase(specBody, phase)) {
      console.log(`[curious] injecting Agent steering into ${phase} prompt`);
    }

    const prompt = buildPrompt({
      phase,
      specPath: this.config.specPath,
      specRelPath: relativeToRoot(this.config.projectRoot, this.config.specPath),
      specBody,
      cycle: state.cycle,
      cwd: this.config.cwd,
      projectRoot: this.config.projectRoot,
      agents,
      lastSummary: this.lastSummary,
      history: state.history,
    });

    console.log(`\n[curious] ── cycle ${state.cycle} · ${phase} ──`);

    if (!this.agent) {
      throw new Error("Agent not connected");
    }

    const startedAt = new Date().toISOString();
    let runId = "";
    let status: CycleRecord["status"] = "error";
    let summary: string | undefined;

    try {
      const sendOptions: SendOptions = {
        onStep: this.opts.verbose
          ? ({ step }) => {
              console.log(`[curious] step ${step.type}`);
            }
          : undefined,
      };

      if (this.shouldForceLocalRun(state)) {
        sendOptions.local = { force: true };
        console.log("[curious] expiring any stuck local run before send");
        state.needsForceNextSend = false;
      }

      const run = await this.sendPrompt(prompt, sendOptions);
      runId = run.id;
      console.log(`[curious] run ${runId}`);
      console.log(
        "[curious] agent working (tool progress below; use --verbose for full text)…",
      );

      const statusStop = run.onDidChangeStatus((status) => {
        console.log(`[curious] run status → ${status}`);
      });

      this.recoveryCancel = false;
      const guard = installConnectionGuard(run, () => {
        this.recoveryCancel = true;
      });

      try {
        await consumeRunStream(run, {
          verbose: this.opts.verbose,
          progress: true,
          signal: guard.abort.signal,
        });

        const result = await run.wait();

        status = result.status;
        summary = result.result;
        this.lastSummary = summary;

        if (result.status === "error") {
          const errorReason = formatRunErrorSummary(result.result);
          state.lastError =
            errorReason ?? `Run ${runId} ended with error`;
          console.error(`[curious] run error: ${runId}`);
          await logRunErrorDetails(run);
        } else if (result.status === "cancelled") {
          if (this.recoveryCancel || guard.abort.signal.aborted) {
            throw guard.abort.signal.reason ?? new Error("connection lost");
          }
          console.log(`[curious] run cancelled: ${runId}`);
          this.stopping = true;
        } else {
          state.lastError = undefined;
          state.needsForceNextSend = false;
          console.log(
            `[curious] run finished in ${result.durationMs ?? "?"}ms`,
          );
          if (summary) {
            const preview =
              summary.length > 400 ? `${summary.slice(0, 400)}…` : summary;
            console.log(`[curious] result: ${preview}`);
          }
        }
      } finally {
        guard.dispose();
        statusStop();
        this.recoveryCancel = false;
      }
    } catch (err) {
      const message = errorMessage(err);

      if (isTransientError(err)) {
        state.lastError = message;
        state.needsForceNextSend = true;
        console.error(
          `[curious] transient error during ${phase} (will retry same phase in 10s): ${message}`,
        );
        await sleep(10_000);
      } else if (isAgentBusyError(err)) {
        state.lastError = message;
        state.needsForceNextSend = true;
        console.error(
          `[curious] agent busy (will retry ${phase} with force in 5s): ${message}`,
        );
        await sleep(5_000);
      } else if (err instanceof CursorAgentError) {
        state.lastError = message;
        console.error(
          `[curious] agent error: ${message} (retryable=${err.isRetryable})`,
        );
        if (err.isRetryable) {
          await sleep(10_000);
        } else {
          this.stopping = true;
        }
      } else {
        state.lastError = message;
        throw err;
      }
    }

    const record: CycleRecord = {
      cycle: state.cycle,
      phase,
      runId: runId || "unknown",
      status,
      startedAt,
      finishedAt: new Date().toISOString(),
      summary,
    };

    state.history.push(record);
    if (state.history.length > 100) {
      state.history = state.history.slice(-100);
    }
    state.lastRunId = runId || state.lastRunId;

    if (status === "finished") {
      if (phase === "sync") {
        state.cycle += 1;
        state.phase = shouldRunOverseer(state, this.config)
          ? "overseer"
          : nextPhase("sync");
      } else {
        state.phase = nextPhase(phase);
      }
    } else {
      console.log(`[curious] staying on phase "${phase}" until a run finishes successfully`);
    }

    await saveState(this.config.projectRoot, state);
    return state;
  }

  private shouldForceLocalRun(state: CuriousState): boolean {
    if (this.config.runtime !== "local") {
      return false;
    }
    if (state.needsForceNextSend || state.lastError) {
      return true;
    }
    const last = state.history.at(-1);
    return last !== undefined && last.status !== "finished";
  }

  private async sendPrompt(
    prompt: string,
    sendOptions: SendOptions,
  ): Promise<Run> {
    if (!this.agent) {
      throw new Error("Agent not connected");
    }

    try {
      return await this.agent.send(prompt, sendOptions);
    } catch (err) {
      if (
        this.config.runtime === "local" &&
        isAgentBusyError(err) &&
        !sendOptions.local?.force
      ) {
        console.log("[curious] agent busy — retrying send with force");
        return await this.agent.send(prompt, {
          ...sendOptions,
          local: { ...sendOptions.local, force: true },
        });
      }
      throw err;
    }
  }

  private logRoadmapStatus(status: ReturnType<typeof analyzeRoadmap>): void {
    if (status.totalTasks === 0) {
      console.log("[curious] roadmap: no T*/M* tasks found in ## Roadmap");
      return;
    }
    const remaining = formatTaskIdList(status.uncheckedTaskIds);
    console.log(
      `[curious] roadmap: ${status.checkedTasks}/${status.totalTasks} tasks done` +
        (remaining ? ` (remaining: ${remaining})` : ""),
    );
  }

  /** True after a successful sync when every roadmap task is checked off. */
  private async roadmapJustCompleted(state: CuriousState): Promise<boolean> {
    const last = state.history[state.history.length - 1];
    if (last?.phase !== "sync" || last.status !== "finished") {
      return false;
    }

    const status = analyzeRoadmap(
      await readFile(this.config.specPath, "utf8"),
    );
    if (!status.complete) {
      return false;
    }

    console.log(
      `[curious] roadmap complete — all ${status.totalTasks} tasks checked off`,
    );
    return true;
  }

  private printContinueHint(completedLimit: number | undefined): void {
    if (completedLimit === 1) {
      console.log("");
      console.log("[curious] To keep going through the roadmap:");
      console.log("  curious run              # until all roadmap tasks are done");
      console.log("  curious run --cycles 5   # five more full cycles");
      console.log("  curious run --cycle      # one more full cycle");
    }
  }

  private printNextStepHint(state: CuriousState): void {
    const last = state.history[state.history.length - 1];
    if (!last) return;

    if (last.status !== "finished") {
      console.log(
        `[curious] phase "${last.phase}" did not finish successfully — fix and re-run`,
      );
      return;
    }

    console.log(
      `[curious] phase "${last.phase}" done — next phase is "${state.phase}" (cycle ${state.cycle})`,
    );

    if (state.phase === "review") {
      console.log("[curious] tip: npm run review  OR  npm run run:cycle");
    } else if (state.phase === "sync") {
      console.log("[curious] tip: npm run sync  OR  npm run run:cycle");
    } else if (state.phase === "overseer") {
      console.log("[curious] tip: curious run  OR  npm run run");
    } else if (state.phase === "develop") {
      console.log("[curious] tip: npm run develop  OR  npm run run:cycle");
    }
  }
}

export async function printStatus(config: ResolvedConfig): Promise<void> {
  const state = await loadState(config.projectRoot);
  console.log(
    JSON.stringify(
      {
        config: {
          projectRoot: config.projectRoot,
          cwd: config.cwd,
          specPath: config.specPath,
          runtime: config.runtime,
        },
        state,
      },
      null,
      2,
    ),
  );
}

export async function resetState(config: ResolvedConfig): Promise<void> {
  await saveState(config.projectRoot, initialState());
  console.log("[curious] state reset");
}
