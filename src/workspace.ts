import type { ResolvedConfig } from "./config.js";
import { ensureAgentBranch } from "./git-branch.js";

export async function prepareAgentWorkspace(
  config: ResolvedConfig,
): Promise<string | null> {
  const branch = config.agentBranch ?? "curious";
  const enabled = config.ensureAgentBranch !== false;
  return ensureAgentBranch(config.projectRoot, branch, enabled);
}
