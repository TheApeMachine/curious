import { extractSpecSection, stripSpecSection } from "./spec-sections.js";
import { sanitizeSteering } from "./workflow-policy.js";
import type { Phase } from "./types.js";

export const AGENT_STEERING_HEADING = "## Agent steering";

const PHASE_SUBSECTION: Partial<Record<Phase, string>> = {
  develop: "Developer",
  review: "Reviewer",
  sync: "Sync",
};

/** Placeholder / empty steering — do not inject into prompts. */
const NOOP_STEERING =
  /^(none|n\/a|—|-|\.\.\.|not applicable|no active steering|no steering needed)/i;

const BOILERPLATE_LINE =
  /^(overseer-maintained|injected into|optional\.|_optional|<!--)/i;

function isActionableSteering(text: string): boolean {
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const substantive = lines.filter((line) => {
    const body = line.replace(/^[-*]\s*/, "").trim();
    if (!body) return false;
    if (NOOP_STEERING.test(body)) return false;
    if (BOILERPLATE_LINE.test(body)) return false;
    if (body.startsWith("_") && body.endsWith("_")) return false;
    // Template placeholders from examples
    if (body.startsWith("(") && body.endsWith(")")) return false;
    return true;
  });

  return substantive.length > 0;
}

function extractSubsection(section: string, title: string): string | null {
  const pattern = new RegExp(
    `^### ${title}\\s*$([\\s\\S]*?)(?=^### |\\z)`,
    "m",
  );
  const match = section.match(pattern);
  if (!match) return null;
  const trimmed = match[1].trim();
  if (trimmed.length === 0 || !isActionableSteering(trimmed)) {
    return null;
  }
  return trimmed;
}

/** Steering text injected into develop / review / sync prompts. */
export function agentSteeringForPhase(
  specBody: string,
  phase: Phase,
): string | null {
  if (phase === "overseer") {
    return null;
  }

  const section = extractSpecSection(specBody, AGENT_STEERING_HEADING);
  if (!section) {
    return null;
  }

  const subsectionTitle = PHASE_SUBSECTION[phase];
  if (!subsectionTitle) {
    return section;
  }

  const phaseSpecific = extractSubsection(section, subsectionTitle);
  if (phaseSpecific) {
    const { text } = sanitizeSteering(phaseSpecific);
    if (!text.trim() || !isActionableSteering(text)) {
      return null;
    }
    return text;
  }

  // Shared bullets only when there are no ### subsections at all
  const hasSubsections = /^### /m.test(section);
  if (!hasSubsections && isActionableSteering(section)) {
    const { text } = sanitizeSteering(section);
    return isActionableSteering(text) ? text : null;
  }

  return null;
}

export function stripAgentSteering(specBody: string): string {
  return stripSpecSection(specBody, AGENT_STEERING_HEADING);
}

export function formatSteeringPromptBlock(
  phase: Phase,
  steering: string,
): string {
  const role = PHASE_SUBSECTION[phase] ?? phase;
  return [
    `## Agent steering (overseer → ${role})`,
    "",
    "Corrective guidance from the overseer — **only present when something concrete needed improvement**. Follow below in addition to AGENTS.md and the spec; if this block is absent, proceed normally.",
    "",
    steering.trim(),
  ].join("\n");
}
