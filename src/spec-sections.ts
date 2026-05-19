/** Extract a top-level `## Heading` section (content after heading, before next `##`). */
export function extractSpecSection(
  body: string,
  heading: string,
): string | null {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const start = body.match(new RegExp(`^${escaped}\\s*$`, "m"));
  if (!start || start.index === undefined) return null;

  const after = body.slice(start.index + start[0].length);
  const next = after.match(/^## /m);
  const section = next?.index !== undefined ? after.slice(0, next.index) : after;
  const trimmed = section.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Remove a top-level `## Heading` section from the spec body. */
export function stripSpecSection(body: string, heading: string): string {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(
    `^${escaped}\\s*$[\\s\\S]*?(?=^## |\\z)`,
    "m",
  );
  return body.replace(pattern, "").replace(/\n{3,}/g, "\n\n").trim();
}
