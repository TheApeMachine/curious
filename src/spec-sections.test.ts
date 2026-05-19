import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { extractSpecSection, stripSpecSection } from "./spec-sections.js";

describe("extractSpecSection", () => {
  it("returns null when the heading is missing", () => {
    assert.equal(extractSpecSection("# Title\n\nBody only.\n", "## Roadmap"), null);
  });

  it("returns null when the section has no content", () => {
    const body = "## Roadmap\n\n## Progress\n\n- [ ] T1.1\n";
    assert.equal(extractSpecSection(body, "## Roadmap"), null);
  });

  it("extracts content until the next top-level heading", () => {
    const body = [
      "## Vision",
      "",
      "Goals here.",
      "",
      "## Roadmap",
      "",
      "- [ ] T1.1 — task",
      "",
      "## Progress",
      "",
      "Active work.",
    ].join("\n");

    assert.equal(extractSpecSection(body, "## Roadmap"), "- [ ] T1.1 — task");
    assert.equal(extractSpecSection(body, "## Vision"), "Goals here.");
  });

  it("extracts through end of file when no following heading", () => {
    const body = "## Constraints\n\nHuman commits only.\n";
    assert.equal(extractSpecSection(body, "## Constraints"), "Human commits only.");
  });

  it("requires an exact heading match (## vs ###)", () => {
    const body = "### Roadmap\n\nSub content.\n\n## Roadmap\n\n- [ ] T1.1\n";
    assert.equal(extractSpecSection(body, "## Roadmap"), "- [ ] T1.1");
    assert.equal(extractSpecSection(body, "### Roadmap"), "Sub content.");
    assert.equal(extractSpecSection(body, "## Progress"), null);
  });

  it("matches headings with regex-special characters", () => {
    const body = "## Agent steering (optional)\n\n- Fix tests\n\n## Roadmap\n\nDone.\n";
    assert.equal(
      extractSpecSection(body, "## Agent steering (optional)"),
      "- Fix tests",
    );
  });
});

describe("stripSpecSection", () => {
  it("returns trimmed body when the heading is missing", () => {
    const body = "## Vision\n\nGoals.\n";
    assert.equal(stripSpecSection(body, "## Roadmap"), body.trim());
  });

  it("removes a middle section and keeps surrounding sections", () => {
    const body = [
      "## Vision",
      "",
      "Goals.",
      "",
      "## Roadmap",
      "",
      "- [ ] T1.1",
      "",
      "## Progress",
      "",
      "Next task.",
    ].join("\n");

    const stripped = stripSpecSection(body, "## Roadmap");
    assert.match(stripped, /^## Vision\n\nGoals\.\n\n## Progress\n\nNext task\.$/);
    assert.doesNotMatch(stripped, /## Roadmap/);
    assert.doesNotMatch(stripped, /T1\.1/);
  });

  it("removes a trailing section when followed by another heading", () => {
    const body = "## Vision\n\nGoals.\n\n## Open questions\n\n1. TBD\n\n## Roadmap\n\nTasks.\n";
    const stripped = stripSpecSection(body, "## Open questions");
    assert.equal(stripped, "## Vision\n\nGoals.\n\n## Roadmap\n\nTasks.");
  });

  it("collapses excess blank lines after removal", () => {
    const body = "## A\n\nContent.\n\n\n\n## B\n\nTail.\n";
    const stripped = stripSpecSection(body, "## A");
    assert.equal(stripped, "## B\n\nTail.");
  });

  it("trims leading and trailing whitespace from the result", () => {
    const body = "\n\n## Vision\n\nGoals.\n\n## Roadmap\n\nTasks.\n\n";
    assert.equal(stripSpecSection(body, "## Vision"), "## Roadmap\n\nTasks.");
  });

  it("strips headings with regex-special characters", () => {
    const body = "## Agent steering (optional)\n\nBullet.\n\n## Roadmap\n\nTasks.\n";
    const stripped = stripSpecSection(body, "## Agent steering (optional)");
    assert.equal(stripped, "## Roadmap\n\nTasks.");
  });
});
