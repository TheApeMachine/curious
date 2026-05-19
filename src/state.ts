import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { CuriousState, Phase } from "./types.js";

const STATE_DIR = ".curious";
const STATE_FILE = "state.json";

export function statePath(cwd: string): string {
  return path.join(cwd, STATE_DIR, STATE_FILE);
}

export function initialState(phase: Phase = "develop"): CuriousState {
  return {
    version: 1,
    phase,
    cycle: 0,
    running: false,
    history: [],
    updatedAt: new Date().toISOString(),
  };
}

export async function loadState(cwd: string): Promise<CuriousState> {
  try {
    const raw = await readFile(statePath(cwd), "utf8");
    return JSON.parse(raw) as CuriousState;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      return initialState();
    }
    throw err;
  }
}

export async function saveState(cwd: string, state: CuriousState): Promise<void> {
  const file = statePath(cwd);
  await mkdir(path.dirname(file), { recursive: true });
  state.updatedAt = new Date().toISOString();
  await writeFile(file, JSON.stringify(state, null, 2), "utf8");
}

export function nextPhase(current: Phase): Phase {
  switch (current) {
    case "develop":
      return "review";
    case "review":
      return "sync";
    case "sync":
      return "develop";
    case "overseer":
      return "develop";
  }
}
