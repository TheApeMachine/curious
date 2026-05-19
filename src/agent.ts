import {
  Agent,
  ConfigurationError,
  CursorAgentError,
  type AgentOptions,
  type SDKAgent,
} from "@cursor/sdk";
import { GIT_POLICY_SUBAGENT } from "./git-policy.js";
import { CURIOUS_MODEL } from "./model.js";
import type { CuriousConfig } from "./types.js";

function isAgentNotFoundError(err: unknown): boolean {
  if (!(err instanceof CursorAgentError)) {
    return false;
  }

  if (err.code === "unknown_agent") {
    return true;
  }

  if (err instanceof ConfigurationError && err.operation === "Agent.resume") {
    return /not found/i.test(err.message);
  }

  return /agent .+ not found/i.test(err.message);
}

export function buildAgentOptions(config: CuriousConfig, agentId?: string): AgentOptions {
  const apiKey = config.apiKey ?? process.env.CURSOR_API_KEY;
  if (!apiKey) {
    throw new Error(
      "Missing CURSOR_API_KEY. Set it in the environment or curious.config.json (apiKey).",
    );
  }

  const options: AgentOptions = {
    apiKey,
    model: CURIOUS_MODEL,
    name: config.agentName ?? "curious-dev-loop",
    agentId,
    agents: {
      developer: {
        description:
          "Implements one roadmap task: code, tests, benchmarks. Use during develop phase.",
        prompt: `You are the developer. Implement one spec roadmap task with tests on this host only.
AGENTS.md is inlined in the parent prompt — follow it exactly. Paste host-runnable test output.
Deliver in the working tree; human commits. When in doubt, read files — they are the source of truth.
Do not edit Roadmap/Progress sections. ${GIT_POLICY_SUBAGENT}`,
        model: "inherit",
      },
      reviewer: {
        description:
          "Reviews the developer's work against spec and roadmap. Use during review phase.",
        prompt: `You are the reviewer. Audit the working tree against spec/SPEC.md and AGENTS.md.
PASS verification on host-runnable tests only; uncommitted work is OK; verify claims by reading files.
Output the review-verdict block. OVERALL: PASS only if all six criteria pass.
Do not edit code or spec. ${GIT_POLICY_SUBAGENT}`,
        model: "inherit",
      },
      overseer: {
        description:
          "Meta alignment: failure patterns, spec drift, checkbox backtracking, roadmap/Progress fixes. Use during overseer phase.",
        prompt: `You are the overseer. Analyze history and files for drift; backtrack misaligned Roadmap/Progress checkboxes when evidence is clear.
Edit spec/SPEC.md when needed. Agent steering is optional — add only for concrete corrective guidance; clear when aligned.
Emit overseer-verdict. Do not edit source code. ${GIT_POLICY_SUBAGENT}`,
        model: "inherit",
      },
    },
  };

  if (config.runtime === "local") {
    options.local = {
      cwd: config.cwd,
      settingSources: config.settingSources,
    };
  } else {
    if (!config.cloud?.repos?.length) {
      throw new Error("Cloud runtime requires curious.config.json cloud.repos.");
    }
    options.cloud = {
      repos: config.cloud.repos,
      autoCreatePR: config.cloud.autoCreatePR ?? false,
      skipReviewerRequest: config.cloud.skipReviewerRequest ?? true,
      workOnCurrentBranch: config.cloud.workOnCurrentBranch ?? false,
    };
  }

  return options;
}

export async function connectAgent(
  config: CuriousConfig,
  persistedAgentId?: string,
): Promise<SDKAgent> {
  const options = buildAgentOptions(config, config.agentId ?? persistedAgentId);
  const stableId = config.agentId ?? persistedAgentId;

  if (stableId) {
    try {
      return await Agent.resume(stableId, options);
    } catch (err) {
      if (!isAgentNotFoundError(err)) {
        throw err;
      }
      console.log(
        `[curious] agent ${stableId} not found locally; creating with stable id`,
      );
    }
  }

  return Agent.create(options);
}
