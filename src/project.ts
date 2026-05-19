import { access, readFile } from "node:fs/promises";
import path from "node:path";

export interface AgentsDocument {
  path: string;
  relPath: string;
  content: string;
}

export const DEFAULT_SPEC_REL = "spec/SPEC.md";
export const CONFIG_FILENAME = "curious.config.json";
export const AGENTS_FILENAME = "AGENTS.md";
export const README_FILENAME = "README.md";

export interface DiscoveredProject {
  projectRoot: string;
  specPath: string;
  hasSpec: boolean;
  configPath?: string;
}

export async function pathExists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Project root is the directory you run `curious` from (or CURIOUS_CWD).
 * Spec is always `<projectRoot>/spec/SPEC.md`.
 */
export async function resolveProjectAtDirectory(
  directory: string,
): Promise<DiscoveredProject> {
  const projectRoot = path.resolve(directory);
  const specPath = path.join(projectRoot, DEFAULT_SPEC_REL);
  const configPath = path.join(projectRoot, CONFIG_FILENAME);

  return {
    projectRoot,
    specPath,
    hasSpec: await pathExists(specPath),
    configPath: (await pathExists(configPath)) ? configPath : undefined,
  };
}

/**
 * Optional: walk parent directories (set CURIOUS_DISCOVER=parents).
 */
export async function discoverProjectInParents(
  startDir: string,
): Promise<DiscoveredProject | null> {
  let directory = path.resolve(startDir);

  for (;;) {
    const resolved = await resolveProjectAtDirectory(directory);
    if (resolved.hasSpec) {
      return resolved;
    }
    if (await pathExists(path.join(directory, README_FILENAME))) {
      return resolved;
    }

    const parent = path.dirname(directory);
    if (parent === directory) {
      return null;
    }
    directory = parent;
  }
}

export function shouldDiscoverParents(): boolean {
  return process.env.CURIOUS_DISCOVER === "parents";
}

/**
 * Load AGENTS.md from project root, then agent cwd. Returns full file content.
 */
export async function loadAgentsDocument(
  projectRoot: string,
  agentCwd: string,
): Promise<AgentsDocument | undefined> {
  const candidates = [
    path.join(projectRoot, AGENTS_FILENAME),
    path.join(agentCwd, AGENTS_FILENAME),
  ];

  for (const absolutePath of candidates) {
    if (!(await pathExists(absolutePath))) {
      continue;
    }

    const content = await readFile(absolutePath, "utf8");
    return {
      path: absolutePath,
      relPath: relativeToRoot(projectRoot, absolutePath),
      content,
    };
  }

  return undefined;
}

export function relativeToRoot(projectRoot: string, absolutePath: string): string {
  const relative = path.relative(projectRoot, absolutePath);
  return relative || ".";
}

export function slugFromPath(projectRoot: string): string {
  const base = path.basename(projectRoot);
  const slug = base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || "project";
}
