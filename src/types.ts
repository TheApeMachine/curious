export interface ModelSelection {
  id: string;
  params?: Array<{ id: string; value: string }>;
}

export type Phase = "develop" | "review" | "sync";

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
  /** Load .cursor project settings (MCP, agents, hooks). */
  settingSources?: Array<"project" | "user" | "team" | "mdm" | "plugins" | "all">;
  cloud?: {
    repos: Array<{ url: string; startingRef?: string }>;
    autoCreatePR?: boolean;
    skipReviewerRequest?: boolean;
    workOnCurrentBranch?: boolean;
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
  history: CycleRecord[];
  updatedAt: string;
}
