export interface ModelSelection {
  id: string;
  params?: Array<{ id: string; value: string }>;
}

export type Phase = "develop" | "review" | "sync" | "overseer";

export type RuntimeKind = "local" | "cloud";

export interface CuriousConfig {
  /** Absolute path to the living spec (markdown). */
  specPath: string;
  /** Working directory for local agents, or target repo root. */
  cwd: string;
  runtime: RuntimeKind;
  /** Always composer-2.5 at runtime; field exists for SDK typing only. */
  model: ModelSelection;
  apiKey?: string;
  /** Stable agent id so runs survive orchestrator restarts. */
  agentId?: string;
  agentName?: string;
  /** Milliseconds to wait between completed cycles. */
  cycleDelayMs: number;
  /** Stop after this many full develop→review→sync cycles (0 = unlimited). */
  maxCycles: number;
  /** Run overseer after sync every N completed task cycles (0 = disable interval). */
  overseerEveryNCycles: number;
  /** Run overseer when this many consecutive review FAILs occur (0 = disable). */
  overseerOnReviewFailStreak: number;
  /** Git branch Curious checks out before agent work (default: curious). */
  agentBranch?: string;
  /** When false, skip automatic branch switch (default: true). */
  ensureAgentBranch?: boolean;
  /** Load .cursor project settings (MCP, agents, hooks). */
  settingSources?: Array<"project" | "user" | "team" | "mdm" | "plugins" | "all">;
  cloud?: {
    repos: Array<{ url: string; startingRef?: string }>;
    autoCreatePR?: boolean;
    skipReviewerRequest?: boolean;
    workOnCurrentBranch?: boolean;
  };
  /** Fine-tuning export settings (opt-in; CLI `curious harvest` works regardless). */
  harvest?: {
    enabled?: boolean;
    /** Output file or directory (default `.curious/harvest/`). */
    output?: string;
  };
}

export interface CycleRecord {
  cycle: number;
  phase: Phase;
  runId: string;
  status: "finished" | "error" | "cancelled";
  startedAt: string;
  finishedAt: string;
  summary?: string;
}

export interface CuriousState {
  version: 1;
  agentId?: string;
  phase: Phase;
  cycle: number;
  running: boolean;
  lastRunId?: string;
  lastError?: string;
  /** Set after stream/crash errors; next local send uses `force` to clear a wedged run. */
  needsForceNextSend?: boolean;
  history: CycleRecord[];
  updatedAt: string;
}
